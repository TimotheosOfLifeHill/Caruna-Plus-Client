import json
import logging
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import List

import requests
from cachetools import TTLCache, cached
from dateutil.relativedelta import relativedelta
from requests import get

from carunaplusservice.api_exceptions import InvalidApiResponseException

from .api_response import MeasurementResponse
from .carunaplus_session import CarunaPlusSession
from .const import BASE_URL, HTTP_READ_TIMEOUT


# TODO: consider moving all calculation functions somewhere else - they are not related to CarunaPlusApiClient
class CarunaPlusApiClient:
    _latest_login_time: datetime = None
    _carunaPlusSession: CarunaPlusSession = None
    _margin: float = None
    _selected_delivery_site_id: str = None
    _selected_delivery_site_assetid: str = None
    _selected_contract = None
    _all_active_contracts = None

    def _json_serializer(value):
        if isinstance(value, datetime):
            return value.strftime("%Y%m%d%H%M%S")
        else:
            return value.__dict__

    def parse_hourly_measurements(self, response_json_text: str):
        """Parse the hourly measurements JSON response from Caruna Plus API."""
        try:
            hourly_measurements = json.loads(response_json_text)
            if isinstance(hourly_measurements, list):
                processed_measurements = defaultdict(list)
                for measurement in hourly_measurements:
                    date = measurement["timestamp"].split("T")[0]
                    processed_measurement = {
                        "timestamp": measurement["timestamp"],
                        "totalConsumption": measurement["totalConsumption"],
                        "invoicedConsumption": measurement["invoicedConsumption"],
                        "totalFee": measurement["totalFee"],
                        "distributionFee": measurement["distributionFee"],
                        "distributionBaseFee": measurement["distributionBaseFee"],
                        "electricityTax": measurement["electricityTax"],
                        "valueAddedTax": measurement["valueAddedTax"],
                        "temperature": measurement["temperature"],
                        "statuses": measurement["statuses"],
                    }
                    processed_measurements[date].append(processed_measurement)
                return dict(processed_measurements)
            else:
                logging.error("Expected a list of measurements")
                return {}
        except json.JSONDecodeError as err:
            logging.error(f"Error decoding JSON: {err}")
            return {}

    def __init__(self, tax: float = None):
        """Initializes the CarunaPlusApiClient with a tax rate"""
        self._tax = 0.255 if tax is None else tax

    def login_and_init(self, username, password):
        """Login to Caruna Plus. Creates a new session when called."""
        self._carunaPlusSession = CarunaPlusSession(username, password).login()
        self._latest_login_time = datetime.now()
        self._refresh_api_client_state()
        return self

    def is_session_valid(self):
        """If the latest login has happened within the last hour, then the session should be valid and ready to go"""
        if self._latest_login_time is None:
            return False
        now = datetime.now()
        is_latest_login_within_hour = (
            now - timedelta(hours=1) <= self._latest_login_time <= now
        )
        return is_latest_login_within_hour

    def close(self):
        if self._carunaPlusSession is not None:
            self._carunaPlusSession.close()

    def _get_hourly_measurement_data_for_date(
        self, start_date: date, end_date: date
    ) -> list:
        # hourly_prices_response = self.get_hourly_spot_prices_between_dates(start_date, end_date)
        # if not hourly_prices_response.interval: return []
        # retain the hourly-price/hourly-measurement pairs (list ordering matters!) by assigning invalid items None
        # hourly_prices = list(map(lambda price: price if price.status == 'valid' else None, hourly_prices_response.interval.measurements))
        hourly_measurements_data = self.get_hourly_measurements_between_dates(
            start_date, end_date
        )
        if not hourly_measurements_data:
            return []
        hourly_measurements = list(
            map(
                lambda measurement: measurement
                if measurement["statuses"]["totalConsumption"] == 150
                else None,
                hourly_measurements_data,
            )
        )
        length = hourly_measurements.__len__()
        if length == 0:
            return []
        hourly_consumption_costs = []
        for i in range(length):
            # hourly_price = hourly_prices[i]
            hourly_measurement = hourly_measurements[i]
            # if hourly_price is None or hourly_measurement is None: continue
            # hourly_price_with_tax_and_margin = hourly_price.value+self._margin
            hourly_consumption_costs.append(
                (abs(hourly_measurement["totalConsumption"]))
            )
        return hourly_consumption_costs

    def calculate_impact_of_usage_between_dates(
        self, start_date: date, end_date: date
    ) -> float:
        """Calculate the price impact of your usage based on hourly consumption and hourly spot prices

        The price impact increases or decreases your contract's unit price in certain contracts
        such as the Caruna Plus Smart Electricity Guarantee contract
        https://www.helen.fi/en/electricity/electricity-products-and-prices/smart-electricity-guarantee
        A negative number decreases and a positive number increases the base price.

        According to Caruna Plus , the impact is calculated with formula (A-B) / E = c/kWh, where
        A = the sum of hourly consumption multiplied with the hourly price (i.e. your weighted average price of each hour)
        B = total consumption multiplied with the whole month's average market price (i.e. your average price of the whole month)
        E = total consumption
        """
        hourly_prices_response = self.get_hourly_measurements_between_dates(
            start_date, end_date
        )

        if not isinstance(hourly_prices_response, list):
            return 0.0

        # if not hourly_prices_response["timestamp"]<>"":
        #     return 0.0
        # retain the hourly-price/hourly-measurement pairs (list ordering matters!) by assigning invalid items None
        hourly_prices = [
            {"timestamp": price["timestamp"], "price": price["totalFee"]}
            for price in hourly_prices_response
            if price["statuses"]["totalConsumption"] == 150
        ]
        hourly_measurements = [
            {
                "timestamp": measurement["timestamp"],
                "measurement": measurement["totalConsumption"],
            }
            for measurement in hourly_prices_response
            if measurement["statuses"]["totalConsumption"] == 150
        ]

        # NotNeeded hourly_prices = list(map(lambda price: price if price.status == 'valid' else None, hourly_prices_response.interval.measurements))
        # NotNeeded hourly_measurements_response = self.get_hourly_measurements_between_dates(start_date, end_date)
        # NotNeeded if not hourly_measurements_response.intervals or not hourly_measurements_response.intervals.electricity: return 0.0
        # NotNeeded hourly_measurements = list(map(lambda measurement: measurement if measurement.status == 'valid' else None, hourly_measurements_response.intervals.electricity[0].measurements))
        length = min(hourly_prices.__len__(), hourly_measurements.__len__())
        # NotNeeded if length == 0: return 0.0
        # NotNeeded hourly_prices_without_nones = list(filter(lambda price: price is not None, hourly_prices))
        # NotNeeded hourly_measurements_without_nones = list(filter(lambda measurement: measurement is not None, hourly_measurements))
        hourly_weighted_consumption_prices = []
        for i in range(length):
            hourly_price = hourly_prices[i]
            hourly_measurement = hourly_measurements[i]
            if hourly_price is None or hourly_measurement is None:
                continue
            hourly_weighted_consumption_prices.append(
                (abs(hourly_price["price"] * hourly_measurement["measurement"]))
            )

        if not hourly_weighted_consumption_prices:
            return 0.0

        monthly_average_price = sum(hourly_price["price"]) / hourly_prices.__len__()
        total_consumption = sum(hourly_measurement["measurement"])
        total_hourly_weighted_consumption_prices = sum(
            hourly_weighted_consumption_prices
        )
        total_consumption_average_price = monthly_average_price * total_consumption

        impact = (
            total_hourly_weighted_consumption_prices - total_consumption_average_price
        ) / total_consumption
        # impact = 0
        return impact

    @cached(cache=TTLCache(maxsize=24, ttl=3600))
    def get_daily_measurements_for_month(
        self, year: str, month: str
    ) -> MeasurementResponse:
        """Get electricity measurements for each day of the wanted month of the on-going year."""

        delivery_site_assetid = self._get_selected_delivery_site_assetid_for_api()

        daily_measurement_for_month = self.get_daily_consumption_for_month(
            delivery_site_assetid, year, month
        )

        return daily_measurement_for_month

    @cached(cache=TTLCache(maxsize=24, ttl=3600))
    def get_daily_measurements_between_dates(
        self, start: date, end: date
    ) -> MeasurementResponse:
        """Get electricity measurements for each day of the wanted month of the on-going year."""
        delivery_site_assetid = self._get_selected_delivery_site_assetid_for_api()

        # monthly_measurement_for_year = self.get_monthly_consumption_for_year(delivery_site_assetid, start.year)
        # daily_measurement_for_month = self.get_daily_consumption_for_month(delivery_site_assetid, start.year, start.month)
        hourly_measurement_day = self.get_hourly_consumption_for_day(
            delivery_site_assetid, start.year, start.month, start.day
        )
        # hour_of_day_measurement = self.get_hour_of_day_consumption(delivery_site_assetid, start.year, start.month, start.day, "22:00:00")

        # quarterly_measurement = self.get_quarterly_consumption_for_hour(delivery_site_assetid, "2024", "12","28","22:00:00")

        return hourly_measurement_day

    @cached(cache=TTLCache(maxsize=24, ttl=3600))
    def get_daily_measurements_between_dates_old(
        self, start: date, end: date
    ) -> MeasurementResponse:
        """Get electricity measurements for each day of the wanted month of the on-going year."""

        previous_day = start + relativedelta(days=-1)
        start_time = f"{previous_day}T22:00:00+00:00"
        end_time = f"{end}T21:59:59+00:00"
        delivery_site_id = self._get_selected_delivery_site_id_for_api()
        delivery_site_assetid = self._get_selected_delivery_site_assetid_for_api()
        measurements_params = {
            "begin": start_time,
            "end": end_time,
            "resolution": "day",
            "delivery_site_id": delivery_site_id,
            "allow_transfer": "true",
        }

        measurements_url = self._get_measurements_endpoint()

        response_json_text = get(
            measurements_url,
            measurements_params,
            headers=self._api_request_headers(),
            timeout=HTTP_READ_TIMEOUT,
        ).text
        daily_measurement: MeasurementResponse = MeasurementResponse(
            **json.loads(response_json_text)
        )

        return daily_measurement

    @cached(cache=TTLCache(maxsize=2, ttl=3600))
    def get_monthly_measurements_by_year(self, year: int) -> MeasurementResponse:
        """Get electricity measurements for each month of the selected year."""

        delivery_site_assetid = self._get_selected_delivery_site_assetid_for_api()

        response_json_text = self.get_monthly_consumption_for_year(
            delivery_site_assetid, year
        )
        monthly_measurement = response_json_text

        return monthly_measurement

    @cached(cache=TTLCache(maxsize=24, ttl=3600))
    def get_monthly_consumption_for_year(self, metering_point: str, year: str):
        """Get the consumption data for the specified metering point for one day"""
        try:
            url = (
                f"{BASE_URL}/api/customers/{self._carunaPlusSession.customer}/assets/{metering_point}/energy"
                f"?year={year}&timespan=yearly"
            )
            r = self._carunaPlusSession._loginSession.get(
                url,
                headers={"Authorization": f"Bearer {self._carunaPlusSession.token}"},
            )
            r.raise_for_status()  # Raise an HTTPError for bad responses
            logging.info("Consumption data retrieved successfully")
            return r.json()
        except requests.exceptions.HTTPError as http_err:
            logging.error(f"HTTP error occurred: {http_err}")
        except requests.exceptions.RequestException as req_err:
            logging.error(f"Request error occurred: {req_err}")
        except Exception as err:
            logging.error(f"Unexpected error occurred: {err}")
        return None

    @cached(cache=TTLCache(maxsize=24, ttl=3600))
    def get_daily_consumption_for_month(
        self, metering_point: str, year: str, month: str
    ):
        """Get the consumption data for the specified metering point for one day"""
        try:
            url = (
                f"{BASE_URL}/api/customers/{self._carunaPlusSession.customer}/assets/{metering_point}/energy"
                f"?year={year}&month={month}&timespan=monthly"
            )
            r = self._carunaPlusSession._loginSession.get(
                url,
                headers={"Authorization": f"Bearer {self._carunaPlusSession.token}"},
            )
            r.raise_for_status()  # Raise an HTTPError for bad responses
            logging.info("Consumption data retrieved successfully")
            return r.json()
        except requests.exceptions.HTTPError as http_err:
            logging.error(f"HTTP error occurred: {http_err}")
        except requests.exceptions.RequestException as req_err:
            logging.error(f"Request error occurred: {req_err}")
        except Exception as err:
            logging.error(f"Unexpected error occurred: {err}")
        return None

    @cached(cache=TTLCache(maxsize=24, ttl=3600))
    def get_hour_of_day_consumption(
        self, metering_point: str, year: str, month: str, day: str, hour: str
    ):
        """Get the consumption data for the specified metering point for one day"""
        try:
            url = (
                f"{BASE_URL}/api/customers/{self._carunaPlusSession.customer}/assets/{metering_point}/energy"
                f"?year={year}&month={month}&day={day}&hour={hour}&timespan=hourly"
            )
            r = self._carunaPlusSession._loginSession.get(
                url,
                headers={"Authorization": f"Bearer {self._carunaPlusSession.token}"},
            )
            r.raise_for_status()  # Raise an HTTPError for bad responses
            logging.info("Consumption data retrieved successfully")
            return r.json()
        except requests.exceptions.HTTPError as http_err:
            logging.error(f"HTTP error occurred: {http_err}")
        except requests.exceptions.RequestException as req_err:
            logging.error(f"Request error occurred: {req_err}")
        except Exception as err:
            logging.error(f"Unexpected error occurred: {err}")
        return None

    @cached(cache=TTLCache(maxsize=24, ttl=3600))
    def get_hourly_consumption_for_day(
        self, metering_point_assetid: str, year: str, month: str, day: str
    ):
        """Get the consumption data for the specified metering point for one day"""
        try:
            url = (
                f"{BASE_URL}/api/customers/{self._carunaPlusSession.customer}/assets/{metering_point_assetid}/energy"
                f"?year={year}&month={month}&day={day}&timespan=daily"
            )
            r = self._carunaPlusSession._loginSession.get(
                url,
                headers={"Authorization": f"Bearer {self._carunaPlusSession.token}"},
            )
            r.raise_for_status()  # Raise an HTTPError for bad responses
            logging.info(
                f"Consumption data retrieved successfully for {year}-{month}-{day} for metering point asset {metering_point_assetid}"
            )
            return r.json()
        except requests.exceptions.HTTPError as http_err:
            logging.error(f"HTTP error occurred: {http_err}")
        except requests.exceptions.RequestException as req_err:
            logging.error(f"Request error occurred: {req_err}")
        except Exception as err:
            logging.error(f"Unexpected error occurred: {err}")
        return None

    @cached(cache=TTLCache(maxsize=24, ttl=3600))
    def get_quarterly_consumption_for_hour(
        self, metering_point: str, year: str, month: str, day: str, hour: str
    ):
        """Get the consumption data for the specified metering point for one day"""
        try:
            url = (
                f"{BASE_URL}/api/customers/{self._carunaPlusSession.customer}/assets/{metering_point}/energy"
                f"?year={year}&month={month}&day={day}&hour={hour}&timespan=daily"
            )
            r = self._carunaPlusSession._loginSession.get(
                url,
                headers={"Authorization": f"Bearer {self._carunaPlusSession.token}"},
            )
            r.raise_for_status()  # Raise an HTTPError for bad responses
            logging.info("Consumption data retrieved successfully")
            return r.json()
        except requests.exceptions.HTTPError as http_err:
            logging.error(f"HTTP error occurred: {http_err}")
        except requests.exceptions.RequestException as req_err:
            logging.error(f"Request error occurred: {req_err}")
        except Exception as err:
            logging.error(f"Unexpected error occurred: {err}")
        return None

    @cached(cache=TTLCache(maxsize=24, ttl=3600))
    def get_hourly_measurements_between_dates(
        self, start: date, end: date
    ) -> MeasurementResponse:
        """Get electricity spot prices for each hour between given dates."""

        delivery_site_assetid = self._get_selected_delivery_site_assetid_for_api()

        hourly_measurements = []

        current_date = start

        while current_date <= end:
            response_json_text = self.get_hourly_consumption_for_day(
                delivery_site_assetid,
                current_date.year,
                current_date.month,
                current_date.day,
            )
            daily_measurements = response_json_text
            hourly_measurements.extend(daily_measurements)
            current_date += timedelta(days=1)
            # Introduce a delay to prevent flooding the API
            time.sleep(0.5)  # Delay for 0.5 second

        measurements_with_total_consumption = [
            m for m in hourly_measurements if "totalConsumption" in m
        ]
        valid_measurements = [
            m
            for m in measurements_with_total_consumption
            if m["statuses"]["totalConsumption"] == 150
        ]

        if valid_measurements:
            latest_measurement = max(valid_measurements, key=lambda m: m["timestamp"])
            latest_measurement_json = json.dumps(
                latest_measurement, default=self._json_serializer, indent=2
            )
            return latest_measurement_json

        return None

    @cached(cache=TTLCache(maxsize=2, ttl=3600))
    def get_meteringpoint_data_json(self):
        """Get your metering point data."""

        """Get the metering points for the specified customer"""
        try:
            r = self._carunaPlusSession._loginSession.get(
                f"{BASE_URL}/api/customers/{self.get_api_customerid()}/assets",
                headers={"Authorization": f"Bearer {self.get_api_access_token()}"},
            )
            r.raise_for_status()  # Raise an HTTPError for bad responses
            logging.info("Metering points retrieved successfully")
            return r.json()
        except requests.exceptions.HTTPError as http_err:
            logging.error(f"HTTP error occurred: {http_err}")
        except requests.exceptions.RequestException as req_err:
            logging.error(f"Request error occurred: {req_err}")
        except Exception as err:
            logging.error(f"Unexpected error occurred: {err}")
        return None

    def _get_selected_delivery_site_id_for_api(self):
        return str(self._selected_contract["id"])

    def _get_selected_delivery_site_assetid_for_api(self):
        return str(self._selected_contract["assetId"])

    def get_all_delivery_site_ids(self) -> List[int]:
        """Get all delivery site ids from your contracts."""

        self._refresh_api_client_state()
        delivery_sites = list(
            map(lambda contract: str(contract["id"]), self._all_active_contracts)
        )
        return delivery_sites

    def get_all_gsrn_ids(self) -> List[int]:
        """Get all GSRN ids from your contracts."""

        self._refresh_api_client_state()
        gsrn_ids = list(
            map(lambda contract: str(contract["gsrn"]), self._all_active_contracts)
        )
        return gsrn_ids

    def select_delivery_site_if_valid_id(self, delivery_site_id: str = None):
        """Select a delivery site to be used when querying data."""
        delivery_sites = self.get_all_delivery_site_ids()
        gsrn_ids = self.get_all_gsrn_ids()
        found_delivery_site_id = next(
            filter(lambda id: str(id) == delivery_site_id, delivery_sites), None
        )
        if not found_delivery_site_id:
            found_delivery_site_id = next(
                filter(lambda id: str(id) == delivery_site_id, gsrn_ids), None
            )
        if not found_delivery_site_id:
            logging.error(
                f"Cannot select {delivery_site_id} because it does not exist in the active delivery sites list {delivery_sites} or GSRN id list {gsrn_ids}"
            )
            return
        self._selected_delivery_site_id = str(found_delivery_site_id)
        self._refresh_api_client_state()
        self._invalidate_caches()
        logging.warning(f"Delivery site set to '{delivery_site_id}'")

    def get_contract_energy_unit_price(self) -> float:
        """
        Get the fixed unit price for electricity from your contract data. Returns '0.0' for spot electricity contracts
        because the price is not fixed in your contract when using spot.
        """

        self._refresh_api_client_state()
        contract = self._selected_contract
        if not contract:
            raise InvalidApiResponseException("Contract data is empty or None")
        products = contract["products"] if contract else []
        product = next(filter(lambda p: p["product_type"] == "energy", products), None)
        if not product:
            logging.warning(
                "Could not resolve energy price from Caruna Plus API response. Returning 0.0"
            )
            return 0.0
        if not product:
            raise InvalidApiResponseException("Product data is empty or None")
        components = product["components"] if product else []
        energy_unit_price_component = next(
            filter(lambda component: component["name"] == "Energia", components), None
        )
        if not energy_unit_price_component:
            logging.warning(
                "Could not resolve energy price from Caruna Plus API response. Returning 0.0"
            )
            return 0.0
        return energy_unit_price_component["price"]

    def get_transfer_fee(self) -> float:
        """Get the transfer fee price (c/kWh) from your contract data. Returns '0.0' if Caruna Plus is not your transfer company"""

        self._refresh_api_client_state()
        contract = self._selected_contract
        if not contract:
            raise InvalidApiResponseException("Contract data is empty or None")
        products = contract["products"] if contract else []
        product = next(
            filter(lambda p: p["product_type"] == "transfer", products), None
        )
        if not product:
            logging.warning(
                "Could not resolve transfer fees from Caruna Plus API response. Returning 0.0"
            )
            return 0.0
        components = product["components"] if product else []
        transfer_fee_component = next(
            filter(lambda component: component["name"] == "Siirtomaksu", components),
            None,
        )
        if transfer_fee_component is None:
            logging.warning(
                "Could not resolve transfer fees from Caruna Plus API response. Returning 0.0"
            )
            return 0.0
        return transfer_fee_component["price"]

    def get_transfer_base_price(self) -> float:
        """Get the transfer base price (eur) from your contract data. Returns '0.0' if Caruna Plus is not your transfer company"""

        self._refresh_api_client_state()
        contract = self._selected_contract
        if not contract:
            raise InvalidApiResponseException("Contract data is empty or None")
        products = contract["products"] if contract else []
        product = next(
            filter(lambda p: p["product_type"] == "transfer", products), None
        )
        if not product:
            logging.warning(
                "Could not resolve transfer base price from Caruna Plus API response. Returning 0.0"
            )
            return 0.0
        components = product["components"] if product else []
        transfer_base_price_component = next(
            filter(lambda component: component["is_base_price"], components), None
        )
        if transfer_base_price_component is None:
            logging.warning(
                "Could not resolve transfer base price from Caruna Plus API response. Returning 0.0"
            )
            return 0.0
        return transfer_base_price_component["price"]

    def get_api_access_token(self):
        return self._carunaPlusSession.get_access_token()

    def get_api_customerid(self):
        return self._carunaPlusSession.get_customerid()

    def _refresh_api_client_state(self):
        contracts = self.get_meteringpoint_data_json()
        self._all_active_contracts = self._get_all_active_meteringpoints(contracts)

        if self._selected_delivery_site_id is None:
            latest_active_contract = self._get_latest_contract(
                self._all_active_contracts
            )
            self._selected_contract = latest_active_contract
            self._selected_delivery_site_id = latest_active_contract["gsrn"]
        else:
            selected_active_contract = self._get_contract_by_delivery_site_id(
                self._all_active_contracts
            )
            self._selected_contract = selected_active_contract

    def _invalidate_caches(self):
        self.get_daily_measurements_between_dates.cache_clear()
        self.get_monthly_measurements_by_year.cache_clear()
        self.get_hourly_measurements_between_dates.cache_clear()
        self.get_hourly_measurements_between_dates.cache_clear()
        self.get_meteringpoint_data_json.cache_clear()

    def _api_request_headers(self):
        return {
            "Authorization": f"Bearer {self.get_api_access_token()}",
            "Accept": "application/json",
        }

    def set_margin(self, margin: float):
        self._margin = margin

    def _get_all_active_meteringpoints(self, meteringpoints):
        """
        Find all active contracts from a list of contracts
        """
        active_meteringpoints = list(meteringpoints)
        # active_contracts = list(filter(lambda contract: contract["domain"] != "electricity-production", active_contracts))
        return active_meteringpoints

    def _get_contract_by_delivery_site_id(self, contracts):
        """
        Finds a contract from a list of contracts by delivery_site_id.
        """
        active_contracts = self._get_all_active_meteringpoints(contracts)
        if self._selected_delivery_site_id:
            if len(str(self._selected_delivery_site_id)) == 18:
                active_contracts = list(
                    filter(
                        lambda contract: contract["gsrn"]
                        == str(self._selected_delivery_site_id),
                        active_contracts,
                    )
                )
            else:
                active_contracts = list(
                    filter(
                        lambda contract: str(contract["delivery_site"]["id"])
                        == str(self._selected_delivery_site_id),
                        active_contracts,
                    )
                )
        if active_contracts.__len__() > 1:
            logging.warning(
                "Found multiple active Caruna Plus contracts. Using the newest one."
            )
            active_contracts.sort(
                key=lambda contract: datetime.strptime(
                    contract["start_date"], "%Y-%m-%dT%H:%M:%S"
                ),
                reverse=True,
            )
        if active_contracts.__len__() == 0:
            logging.error("No active contracts found")
            return None
        return active_contracts[0]

    def _get_latest_contract(self, contracts):
        """
        Resolves the latest contract from a list of contracts.
        """
        if contracts.__len__() == 0:
            logging.error("No contracts found")
            return None
        # contracts.sort(key=lambda contract: datetime.strptime(contract["start_date"], '%Y-%m-%dT%H:%M:%S'), reverse=True)
        # latest_contract_id = contracts[0]["id"] if contracts else None
        return contracts[0]

    def _date_is_now_or_later(self, end_date_str):
        end_date = datetime.strptime(end_date_str, "%Y-%m-%dT%H:%M:%S")
        now = datetime.now()
        return end_date >= now

    def _get_measurements_endpoint(self):
        if (
            "domain" in self._selected_contract
            and self._selected_contract["domain"] == "electricity-transfer"
        ):
            return self.CARUNAPLUS_API_URL_V16 + self.TRANSFER_ENDPOINT
        return self.CARUNAPLUS_API_URL_V16 + self.MEASUREMENTS_ENDPOINT
