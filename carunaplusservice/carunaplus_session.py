import json
import logging
import re

import requests
from bs4 import BeautifulSoup
from requests import Request, Response, Session

from .const import (
    AUTH_URL,
    BASE_URL,
    HTTP_READ_TIMEOUT,
    LOGIN_API,
    LOGOUT_URL,
    TOKEN_API,
)


class CarunaPlusSession:
    _loginSession: Session = None

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self._loginSession = requests.session()
        self.token = None
        self.user_info = None
        self.customer = None

    def login(self):
        """Login to Caruna+ as a registered user"""
        try:
            url = json.loads(
                self._loginSession.post(
                    LOGIN_API, json={"redirectAfterLogin": BASE_URL, "language": "fi"}
                ).content
            )["loginRedirectUrl"]
            soup = BeautifulSoup(self._loginSession.get(url).content, "lxml")
            post_url = soup.find("meta")["content"][6:]  # type: ignore
            r = self._loginSession.get(AUTH_URL + str(post_url))
            soup = BeautifulSoup(r.content, "lxml")
            action = (
                soup.find("form")["action"][1:][:11]
                + "0-userIDPanel-usernameLogin-loginWithUserID"
            )  # type: ignore

            svars = {
                var["name"]: var.get("value", "")
                for var in soup.findAll("input", type="hidden")
            }

            svars["ttqusername"] = self.username
            svars["userPassword"] = self.password
            svars[soup.find("input", type="submit")["name"]] = "1"  # type: ignore
            extraHeaders = {
                "Wicket-Ajax": "true",
                "Wicket-Ajax-BaseURL": ".",
                "Wicket-FocusedElementId": "loginWithUserID5",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": AUTH_URL,
                "Referer": f"{AUTH_URL}/portal/",
            }
            text = self._loginSession.post(
                AUTH_URL + "/portal" + action, data=svars, headers=extraHeaders
            ).text
            text = text[text.find("CDATA[") + 7 :]
            url = text[: text.find("]")]
            r = self._loginSession.get(AUTH_URL + "/portal" + url)
            soup = BeautifulSoup(r.content, "lxml")
            url = soup.find("meta")["content"][6:]  # type: ignore
            soup = BeautifulSoup(self._loginSession.get(str(url)).content, "lxml")
            action = soup.find("form")["action"]  # type: ignore

            svars = {
                var["name"]: var.get("value", "")
                for var in soup.findAll("input", type="hidden")
            }
            r = self._loginSession.post(action, data=svars)  # type: ignore
            r = self._loginSession.post(
                TOKEN_API, data=r.request.path_url.split("?")[1]
            )
            self.user_info = json.loads(r.text)
            self.customer = self.user_info["user"]["ownCustomerNumbers"][0]
            self.token = self.user_info.get("token")
            logging.info("Login successful")
            return self
        except requests.exceptions.RequestException as e:
            logging.error(f"Request error during login: {e}")
        except Exception as e:
            logging.error(f"Unexpected error during login: {e}")

    def get_customerid(self):
        return self.customer

    def get_access_token(self):
        """Get the access-token to use the Caruna Plus API. It is required to login before the
        token can be accessed
        """
        # if self._loginSession is None:
        #    raise Exception("The session is not active. Log in first")

        # access_token = self._loginSession.cookies.get("access-token")
        # self.user_info = json.loads(r.text)
        # self.customer = self.user_info['user']['ownCustomerNumbers'][0]
        access_token = self.token  # self.user_info.get('token')

        if access_token is None:
            raise Exception("No access token found. Log in first")

        return access_token

    def close(self):
        """Close down the session for the Caruna Plus web service"""
        if self._loginSession is not None:
            self._loginSession.close()
            logging.debug("CarunaPlusSession was closed")

    def _follow_redirects(self, response: Response):
        location_header = response.headers.get("Location")
        if location_header is None:
            location_header = response.headers.get("location")
        if location_header is not None:
            response = self._follow_redirects(
                self._loginSession.get(location_header, timeout=HTTP_READ_TIMEOUT)
            )
            return response
        return response

    def _make_url_request(self, url: str, method: str, data=None, params=None):
        request = Request(method, url)

        if data is not None:
            request.data = data
        if params is not None:
            request.params = params
        prepared_request = self._loginSession.prepare_request(request)

        response = self._loginSession.send(prepared_request, timeout=HTTP_READ_TIMEOUT)

        response = self._follow_redirects(response)

        return response

    def _get_html_input_value(self, soup: BeautifulSoup, attribute_name: str):
        return soup.find("input", {"name": attribute_name}).get("value")

    def _get_html_form_url(self, soup: BeautifulSoup):
        return soup.find("form").attrs["action"]

    def _get_html_form_method(self, soup: BeautifulSoup):
        return soup.find("form").attrs["method"]
