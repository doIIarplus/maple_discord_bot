import base64
from dataclasses import dataclass
import dataclasses
from enum import Enum
import json
import time
import re
from typing import Any, Dict, Generic, List, Optional, TypeVar
import requests

AZURE_POST_ENDPOINT = "https://spookie-text-extract.cognitiveservices.azure.com/formrecognizer/documentModels/prebuilt-document:analyze?api-version=2023-07-31"
AZURE_KEY = "955ee3d2db6e433ebb932ffa9dd8913b"
ENDPOINT_RESPONSE_KEY = "Operation-Location"
MAX_ATTEMPTS = 5


def send_request(filepath: str) -> str:
    with open(filepath, "rb") as file:
        base64_encoded_file = base64.b64encode(file.read()).decode()

    data = {"base64Source": base64_encoded_file}

    headers = {
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Key": AZURE_KEY,
    }

    response = requests.post(
        AZURE_POST_ENDPOINT,
        headers=headers,
        data=json.dumps(data),
    )

    print(response.content)

    result_location = response.headers[ENDPOINT_RESPONSE_KEY]

    is_success = False
    loop_counter = 0

    while not is_success:
        if loop_counter > MAX_ATTEMPTS:
            raise Exception("Exceeded max attempts")

        response = requests.get(
            result_location,
            headers=headers,
        )

        response_json = response.json()
        status = response_json["status"]
        if status == "succeeded":
            return response_json
        else:
            loop_counter += 1
            time.sleep(5)


def preprocess_word(word: str, replace_four: bool) -> str:
    if replace_four:
        return (
            word.replace("+", "")
            .replace("-", "")
            .replace("4", "")
            .replace("&", "")
            .replace("^", "")
            .replace("%", "")
            .split("(")[0]
            .strip()
        )
    else:
        return (
            word.replace("+", "")
            .replace("-", "")
            .replace("^", "")
            .replace("&", "")
            .replace("%", "")
            .replace(",", "")
            .split("(")[0]
            .strip()
        )


def parse_results(
    response_json: Dict[str, Any],
):
    results = {}
    # Table contains all cells, going column by column, row by row
    cells = response_json["analyzeResult"]["tables"][0]["cells"]
    rows = response_json["analyzeResult"]["tables"][0]["rowCount"]
    columns = response_json["analyzeResult"]["tables"][0]["columnCount"]

    print(len(cells))

    ign_column = 0
    culvert_column = 5

    for current_row in range(1, rows):
        ign = None
        culvert = None
        for current_column in range(columns):
            current_cell = get_cell_content(cells, current_row, current_column)
            if current_column == ign_column:
                ign = current_cell.lower()
            elif current_column == culvert_column:
                culvert = current_cell
                results[ign] = 0 if culvert.lower() == "o" else culvert

    return results

def get_cell_content(cells, row, column):
    for cell in cells:
        if cell['rowIndex'] == row and cell['columnIndex'] == column:
            return cell['content']

def main():
    file = "/home/pi/gpq-bot/src/JPEGView_QG2rnnz6tQ.png"
    response = parse_results(send_request(file))
    print(response)


if __name__ == "__main__":
    main()
