import re
import requests
from requests import Request, Response, Session
from bs4 import BeautifulSoup
from .const import HTTP_READ_TIMEOUT,BASE_URL, AUTH_URL, LOGIN_API, TOKEN_API, LOGOUT_URL
import logging
import json


class CarunaPlusSession:

    _session: Session = None

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self._session = requests.session()
        self.token = None
        self.user_info = None
        self.customer = None

    def login(self, username, password):
        """Login to Caruna+ as a registered user"""
        try:
            url = json.loads(self._session.post(LOGIN_API,
                                               json={"redirectAfterLogin": BASE_URL,
                                                     "language": "fi"}).content)["loginRedirectUrl"]
            soup = BeautifulSoup(self._session.get(url).content, 'lxml')
            post_url = soup.find('meta')['content'][6:]  # type: ignore
            r = self._session.get(AUTH_URL + str(post_url))
            soup = BeautifulSoup(r.content, 'lxml')
            action = soup.find('form')['action'][1:][:11] + "0-userIDPanel-usernameLogin-loginWithUserID"  # type: ignore
            svars = {var['name']: var.get('value', '') for var in soup.findAll('input', type="hidden")}
            svars['ttqusername'] = username
            svars['userPassword'] = password
            svars[soup.find('input', type="submit")['name']] = "1"  # type: ignore
            extraHeaders = {
                'Wicket-Ajax': 'true',
                'Wicket-Ajax-BaseURL': '.',
                'Wicket-FocusedElementId': 'loginWithUserID5',
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': AUTH_URL,
                'Referer': f"{AUTH_URL}/portal/"
            }
            text = self._session.post(AUTH_URL + "/portal" + action,
                                     data=svars, headers=extraHeaders).text
            text = text[text.find('CDATA[') + 7:]
            url = text[:text.find(']')]
            r = self._session.get(AUTH_URL + "/portal" + url)
            soup = BeautifulSoup(r.content, 'lxml')
            url = soup.find('meta')['content'][6:]  # type: ignore
            soup = BeautifulSoup(self._session.get(str(url)).content, 'lxml')
            action = soup.find('form')['action']  # type: ignore
            svars = {var['name']: var.get('value', '') for var in soup.findAll('input', type="hidden")}
            r = self._session.post(action, data=svars)  # type: ignore
            r = self._session.post(TOKEN_API, data=r.request.path_url.split("?")[1])
            self.user_info = json.loads(r.text)
            self.customer = self.user_info['user']['ownCustomerNumbers'][0]
            self.token = self.user_info.get('token')
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
        #if self._session is None:
        #    raise Exception("The session is not active. Log in first")

        #access_token = self._session.cookies.get("access-token")
        #self.user_info = json.loads(r.text)
        #self.customer = self.user_info['user']['ownCustomerNumbers'][0]
        access_token = self.token #self.user_info.get('token')
        
        if access_token is None:
            raise Exception("No access token found. Log in first")

        return access_token

    def close(self):
        """Close down the session for the Caruna Plus web service
        """
        if self._session is not None:
            self._session.close()
            logging.debug("CarunaPlusSession was closed")

    def _follow_redirects(self, response: Response):
        location_header = response.headers.get("Location")
        if location_header is None:
            location_header = response.headers.get("location")
        if location_header is not None:
            response = self._follow_redirects(self._session.get(location_header, timeout=HTTP_READ_TIMEOUT))
            return response
        return response

    def _make_url_request(self, url: str, method: str, data=None, params=None):
        request = Request(method, url)

        if data is not None:
            request.data = data
        if params is not None:
            request.params = params
        prepared_request = self._session.prepare_request(request)

        response = self._session.send(prepared_request, timeout=HTTP_READ_TIMEOUT)

        response = self._follow_redirects(response)

        return response

    def _get_html_input_value(self, soup: BeautifulSoup, attribute_name: str):
        return soup.find("input", {"name": attribute_name}).get("value")

    def _get_html_form_url(self, soup: BeautifulSoup):
        return soup.find("form").attrs['action']

    def _get_html_form_method(self, soup: BeautifulSoup):
        return soup.find("form").attrs["method"]

    def _get_tupas_response(self):
        return self._session.get(self.TUPAS_LOGIN_URL, timeout=HTTP_READ_TIMEOUT)

    def _send_login_request(self, username, password):
        # tupas_response = self._get_tupas_response()
        # tupas_soup = BeautifulSoup(tupas_response.text, "html.parser")
        authorization_url = self.AUTHORIZATION_URL #self._get_html_form_url(tupas_soup)
        # AUTHORIZATION_URL
        # authorization_form_method = "POST" #self._get_html_form_method(tupas_soup)
        # authorization_response = self._make_url_request(
        #    authorization_url, authorization_form_method)
                # Start the authentication flow. This page will do some redirects and finally return a JSON object containing
        # a URL we have to visit manually
        # authorization_response = self._make_url_request(authorization_url, 'POST', data={
        #     'language': 'fi',
        #     'redirectAfterLogin': 'https://plus.caruna.fi/',
        # })
        
        authorization_response = self._session.post(authorization_url, json={
            'language': 'fi',
            'redirectAfterLogin': 'https://plus.caruna.fi/',
        })
        authorization_soup = BeautifulSoup(
            authorization_response.text, "html.parser")
        login_url = self.CARUNAPLUS_LOGIN_HOST + \
            self._get_html_form_url(authorization_soup)

        login_payload = {"username": username, "password": password}
        return self._make_url_request(login_url, "POST", login_payload)
    
    def _fix_carunaplus_api_url(self, url):
        fixed_url = re.sub(r"\/v\d+\/", "/" + self.LOGIN_API_VERSION + "/", url)
        return fixed_url.replace("omahelen", "oma.helen")

    def _proceed_to_main_page_from_login_response(self, response: Response):
        access_granted_soup = BeautifulSoup(response.text, "html.parser")
        continue_url = self._get_html_form_url(access_granted_soup)
        continue_param_code = self._get_html_input_value(
            access_granted_soup, "code")
        continue_param_state = self._get_html_input_value(
            access_granted_soup, "state")
        continue_params = {"code": continue_param_code,
                           "state": continue_param_state}
        proceed_link_page_response = self._make_url_request(
            continue_url, "GET", params=continue_params)

        proceed_link_page_soup = BeautifulSoup(
            proceed_link_page_response.text, "html.parser")
        proceed_link_page_link_url = proceed_link_page_soup.find(
            "a").attrs['href']
        auth_response = self._make_url_request(
            self._fix_carunaplus_api_url(proceed_link_page_link_url), "GET")
    
        auth_response_soup = BeautifulSoup(auth_response.text, "html.parser")
        auth_response_url = self._get_html_form_url(auth_response_soup)
        auth_response_param_code = self._get_html_input_value(
            auth_response_soup, "code")
        auth_response_param_state = self._get_html_input_value(
            auth_response_soup, "state")
        auth_response_params = {
            "code": auth_response_param_code, "state": auth_response_param_state}

        self._make_url_request(auth_response_url, "GET", params=auth_response_params)
