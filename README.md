# MLS Roster Profile Parser

This library is used to parse an MLS roster profile PDF document ([example](./data/pdf/2025-05-01.pdf)),
extract the enclosed details, and return a JSON-like structure.

In the process, it attempts to map player and team names to their corresponding American Soccer Analysis IDs
(fetched using [`itscalledsoccer`](https://github.com/AmericanSoccerAnalysis/itscalledsoccer)). It does so
automatically when there is a single evident match, and it prompts the user for confirmation via the console
when there are multiple potential matches.

Throughout, it produces warning messages when a) certain extracted values do not belong to a set of expected
values and/or b) a player or team cannot be confidently mapped to an ID. These warnings represent portions of
the output which may benefit from manual review.

## Installation

```bash
pip install git+https://github.com/AmericanSoccerAnalysis/mls-roster-profiles.git
```

## Sample Usage

```python
from mls_roster_profiles import RosterProfileRelease

release = RosterProfileRelease.from_pdf("./data/pdf/2025-05-01.pdf")
print(release.model_dump_json(indent=2))
```

```json
{
  "release_date": "2025-05-01",
  "teams": [
    {
      "id": "KAqBN0Vqbg",
      "name": "Atlanta United FC",
      "roster_construction_model": "Designated Player Model",
      "players": [
        {
          "id": "raMyAywlMd",
          "name": "Miguel Almirón",
          "roster_slot": "Senior Roster",
          "roster_designation": "Designated Player",
          "current_status": null,
          "contract_through": "2027",
          "option_years": "2028",
          "permanent_transfer_option": null,
          "international_slot": true,
          "convertible_with_tam": false,
          "unavailable": false,
          "canadian_international_slot_exemption": null
        },
        ...
        {
          "id": "9vQ24ABe5K",
          "name": "Adyn Torres",
          "roster_slot": "Supplemental Spot 31",
          "roster_designation": "Homegrown Player",
          "current_status": "Unavailable - On Loan",
          "contract_through": "2027",
          "option_years": "2028",
          "permanent_transfer_option": null,
          "international_slot": false,
          "convertible_with_tam": null,
          "unavailable": true,
          "canadian_international_slot_exemption": null
        }
      ],
      "international_slots": 8,
      "gam_available": 1206065
    }
  ],
  ...
}
```

## Development

Setting up a development environment requires the following dependencies:

1. [Docker](https://www.docker.com/)
2. [Visual Studio Code](https://code.visualstudio.com/)
3. [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

Ensure Docker is running on your machine, and then open the repository folder in Visual Studio Code. You should be prompted to reopen the folder in a container. Click the button to accept. This will configure the development container with all necessary dependencies.

_Note: If you do not receive this prompt, or if the prompt disappears before you are able to click the button, you can instead select the `Dev Containers: Reopen in Container` command from the Command Palette._
