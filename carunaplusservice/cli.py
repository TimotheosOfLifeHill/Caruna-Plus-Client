import json
import logging
from cmd import Cmd
from datetime import date, datetime, timedelta

from .api_client import CarunaPlusApiClient
from .keyring_manager import KeyringManager
from .price_client import CarunaPlusPriceClient

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def _json_serializer(value):
    if isinstance(value, datetime):
        return value.strftime("%Y%m%d%H%M%S")
    else:
        return value.__dict__


class CarunaPlusCLIPrompt(Cmd):
    prompt = "caruna-plus-cli> "
    intro = "Type ? to list commands"

    carunaplus_price_client = CarunaPlusPriceClient()
    tax = 0.255  # 25.5%
    api_client = CarunaPlusApiClient(tax)
    keyring_manager = KeyringManager("caruna-plus-cli")

    def __init__(self, username=None, password=None):
        super(CarunaPlusCLIPrompt, self).__init__()
        self.username = username
        self.password = password

        try:
            self.api_client.login_and_init(self.username, self.password)
        except Exception as e:
            logging.error(f"Failed to initialize API client: {e}")
            raise

    def do_exit(self, input=None):
        """Exit the CLI"""
        self.api_client.close()
        print("Bye")
        return True

    def _parse_dates(self, input):
        try:
            start_date_str, end_date_str = str(input).split(" ")
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            if start_date > end_date:
                raise ValueError("Start date must be before end date")
            return start_date, end_date
        except ValueError as e:
            logging.error(f"Date parsing error: {e}")
            print("Please provide proper start and end dates in format 'YYYY-mm-dd'")
            return None, None

    def do_calculate_the_impact_of_usage_between_dates(self, input=None):
        """Calculate the impact of usage for Caruna Plus Smart Electricity Guarantee contract between a start date and an end date"""
        if input is None:
            print("Please provide proper start and end dates in format 'YYYY-mm-dd'")
            return

        start_date, end_date = self._parse_dates(input)
        if not start_date or not end_date:
            return

        try:
            impact = self.api_client.calculate_impact_of_usage_between_dates(
                start_date, end_date
            )
            print(impact)
        except Exception as e:
            logging.error(f"Error calculating impact of usage: {e}")

    def do_get_latest_hourly_measurements_json(self, input=None):
        """Get the latest electricity measurements as JSON"""
        try:
            end_date = datetime.today().date()
            start_date = end_date - timedelta(days=5)
            latest_hourly_monthly_measurement = (
                self.api_client.get_hourly_measurements_between_dates(
                    start_date, end_date
                )
            )
            latest_measurement_json = latest_hourly_monthly_measurement
            print(latest_measurement_json)
        except Exception as e:
            logging.error(f"Error getting monthly measurements: {e}")

    def do_get_hourly_measurements_between_dates_json(self, input=None):
        """Get the monthly electricity measurements of the previous year as JSON"""
        if input is None:
            print("Please provide proper start and end dates in format 'YYYY-mm-dd'")
            return

        start_date, end_date = self._parse_dates(input)
        if not start_date or not end_date:
            return

        try:
            monthly_measurements = (
                self.api_client.get_hourly_measurements_between_dates(
                    start_date, end_date
                )
            )
            monthly_measurements_json = json.dumps(
                monthly_measurements, default=_json_serializer, indent=2
            )
            print(monthly_measurements_json)
        except Exception as e:
            logging.error(f"Error getting monthly measurements: {e}")

    def do_get_currentyear_monthly_measurements_json(self, input=None):
        """Get the monthly electricity measurements of the on-going year as JSON"""
        try:
            year = date.today().year
            monthly_measurements = self.api_client.get_monthly_measurements_by_year(
                year
            )
            monthly_measurements_json = json.dumps(
                monthly_measurements, default=_json_serializer, indent=2
            )
            print(monthly_measurements_json)
        except Exception as e:
            logging.error(f"Error getting monthly measurements: {e}")

    def do_get_previous_year_monthly_measurements_json(self, input=None):
        """Get the monthly electricity measurements of the previous year as JSON"""
        try:
            year = date.today().year - 1
            monthly_measurements = self.api_client.get_monthly_measurements_by_year(
                year
            )
            monthly_measurements_json = json.dumps(
                monthly_measurements, default=_json_serializer, indent=2
            )
            print(monthly_measurements_json)
        except Exception as e:
            logging.error(f"Error getting monthly measurements: {e}")

    def do_get_previous_month_daily_measurements_json(self, input=None):
        """Get the daily electricity measurements of the previous month of the on-going year as JSON"""
        current_year = date.today().year
        current_month = date.today().month

        if current_month == 1:
            year = current_year - 1
            month = 12
        else:
            year = current_year
            month = current_month - 1

        try:
            daily_measurements = self.api_client.get_daily_measurements_for_month(
                year, month
            )
            daily_measurements_json = json.dumps(
                daily_measurements, default=_json_serializer, indent=2
            )
            print(daily_measurements_json)
        except Exception as e:
            logging.error(f"Error getting daily measurements: {e}")

    def do_get_current_month_daily_measurements_json(self, input=None):
        """Get the daily electricity measurements of the on-going month of the on-going year as JSON"""
        year = date.today().year
        month = date.today().month

        try:
            daily_measurements = self.api_client.get_daily_measurements_for_month(
                year, month
            )
            daily_measurements_json = json.dumps(
                daily_measurements, default=_json_serializer, indent=2
            )
            print(daily_measurements_json)
        except Exception as e:
            logging.error(f"Error getting daily measurements: {e}")

    def do_get_meteringpoint_data_json(self, input=None):
        """Get all your contracts as JSON (includes terminated contracts)"""
        try:
            contract_data_json = self.api_client.get_meteringpoint_data_json()
            contract_data_json_pretty = json.dumps(
                contract_data_json, default=_json_serializer, indent=2
            )
            print(contract_data_json_pretty)
        except Exception as e:
            logging.error(f"Error getting metering point data: {e}")

    def do_get_exchange_margin_price_json(self, input=None):
        """Get margin price for the Exchange Electricity contract type as JSON"""
        try:
            price = self.carunaplus_price_client.get_exchange_prices()
            price_json = json.dumps(price, default=_json_serializer, indent=2)
            print(price_json)
        except Exception as e:
            logging.error(f"Error getting exchange margin price: {e}")

    def do_get_api_access_token(self, input=None):
        """Get your access token for the Caruna Plus API."""
        try:
            access_token = self.api_client.get_api_access_token()
            print(access_token)
        except Exception as e:
            logging.error(f"Error getting API access token: {e}")

    def do_select_delivery_site(self, input=None):
        """Select a delivery site to be used in the api_client."""
        try:
            self.api_client.select_delivery_site_if_valid_id(input)
        except Exception as e:
            logging.error(f"Error selecting delivery site: {e}")

    def do_get_all_delivery_sites(self, input=None):
        """Get all delivery site ids across your active contracts."""
        try:
            delivery_sites = self.api_client.get_all_delivery_site_ids()
            print(delivery_sites)
        except Exception as e:
            logging.error(f"Error getting all delivery sites: {e}")

    def do_get_all_gsrn_ids(self, input=None):
        """Get all gsrn ids across your active contracts."""
        try:
            gsrn_ids = self.api_client.get_all_gsrn_ids()
            print(gsrn_ids)
        except Exception as e:
            logging.error(f"Error getting all GSRN ids: {e}")

    def do_clear_credentials(self, input=None):
        """Clear stored username and password and prompt for new credentials."""
        self.keyring_manager.clear_credentials()
        print("Credentials cleared. Please restart the CLI to set new credentials.")


def main():
    """Main function to start the CLI"""
    print("Log in to Caruna Plus")
    keyring_manager = KeyringManager("caruna-plus-cli")
    username, password = keyring_manager.prompt_for_credentials()

    try:
        CarunaPlusCLIPrompt(username, password).cmdloop()
    except Exception as e:
        logging.error(f"Failed to start CLI: {e}")


if __name__ == "__main__":
    main()
