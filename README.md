# Caruna Plus Client

[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.com/donate/?hosted_button_id=92TWRV5CY5NG6)
[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/TimotheosOfLifeHill)

## Overview

Caruna Plus is a service provided by Caruna, a Finnish electricity distribution company. The service offers customers access to detailed information about their electricity consumption, contracts, and other related data through an online portal and API. The Caruna Plus Client project in your workspace is designed to interact with the Caruna Plus API, allowing users to retrieve and manage their electricity data programmatically.

## How to install and use

Install from [pypi](https://pypi.org/project/caruna-plus-cli/) and run: 
```sh
pip install caruna-plus-cli
caruna-plus-cli
```

Then just enter you Caruna Plus credentials and start entering commands.

Tip: in order to list all the commands within the CLI, enter `?`

### Available functions

| Function name                 | What it does |
|-------------------------------|--------------|
| get_api_access_token          | Get the access token to the Caruna Plus API. With the token, you can make manual curl requests to the API |

### Installing from sources and running the project for local development

First clone this repo.

Use virtual env to keep the project isolated. Developed using Python 3.9.9

1. In the project root folder run `python -m venv .venv`
2. Activate the venv with `source .venv/bin/activate`
3. Install requirements `pip install -r requirements.txt`
4. Launch the CLI as a python module `python -m carunaservice.cli`
5. Enter your username and password as they are prompted
6. Type `?` into the CLI prompt to see all available functions

Deactivate venv when not needed: `deactivate`

## Thanks and relatad

This project, **Caruna Plus Client**, is built upon work from the following repositories and projects:

- **[oma-helen-cli](https://github.com/carohauta/oma-helen-cli)**: An interactive CLI that logs into Oma Helen and offers functions to get contract data or electricity measurement data in JSON format.
- **[pycaruna](https://github.com/kimmolinna/pycaruna)**: Caruna API for Python.
- **[Caruna API client in Go](https://github.com/braincow/gocaruna)**: Go library for interfacing with Caruna API

I appreciate the work of the contributors and maintainers of these projects, as their efforts provided the foundation for my work.

## Attribution

This project uses code, ideas, or assets from the aforementioned repositories under the terms of their respective licenses:

1. **[oma-helen-cli](https://github.com/carohauta/oma-helen-cli)**
   - License: [MIT] ([View License](https://github.com/carohauta/oma-helen-cli?tab=MIT-1-ov-file))

2. **[pycaruna](https://github.com/kimmolinna/pycaruna)**
   - License: [MIT] ([View License](https://github.com/kimmolinna/pycaruna?tab=MIT-1-ov-file))

3. **[gocaruna](https://github.com/braincow/gocaruna)**
   - License: [MIT] ([View License](https://github.com/braincow/gocaruna?tab=MIT-1-ov-file))
  
## License

This project is licensed under the [MIT](./LICENSE) license. See the LICENSE file for details.

When using this project, you are also bound by the terms of the licenses of the referenced repositories and projects. Please ensure compliance with their requirements.

## Acknowledgments

 If you have questions or concerns regarding the usage of code from other repositories, please [contact us](mailto:your-email@example.com).
