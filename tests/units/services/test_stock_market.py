from src.services.stock_market import Moex
from src.models.error import Error
import pytest
import requests
import os
import json


class TestFetchJson:

    @pytest.mark.parametrize("mock_json, expected", [
        ({"data": [1, 2]}, {"data": [1, 2]}),
        ({}, {}),
    ])
    def test_successful_http_get_returns_json_dict(self, mocker, mock_json, expected):
        # Arrange
        mock_response = mocker.Mock()
        mock_response.json.return_value = mock_json
        mock_session = mocker.Mock()
        mock_session.get.return_value = mock_response

        moex = Moex()
        moex.session = mock_session

        url = "https://api.example.com/data"
        params = {"limit": 10, "start": 0}

        # Act
        result = moex._fetch_json(url, params)

        # Assert
        mock_session.get.assert_called_once_with(url, params=params)
        mock_response.raise_for_status.assert_called_once()
        mock_response.json.assert_called_once()
        assert result == expected
        assert isinstance(result, dict)

    @pytest.mark.parametrize("status_code, result_code", [
        (400, 400),
        (500, 500),
        (404, 404),
        (503, 503),
    ])
    def test_http_error_raises_custom_error(self, mocker, status_code, result_code):
        # Arrange
        mock_response = mocker.Mock()
        mock_response.status_code = status_code

        request_exception = requests.RequestException("HTTP Error")
        request_exception.response = mock_response

        mock_session = mocker.Mock()
        mock_session.get.side_effect = request_exception

        moex = Moex()
        moex.session = mock_session

        url = "https://api.example.com/data"
        params = {"limit": 10, "start": 0}

        # Act & Assert
        with pytest.raises(Error) as exc_info:
            moex._fetch_json(url, params)

        error = exc_info.value
        assert error.source == "Moex"
        assert error.source_data == request_exception
        assert error.data == {"url": url, "params": params}
        assert error.description == f"Code: {result_code}"
        mock_session.get.assert_called_once_with(url, params=params)


class TestLoadIndexData:

    @staticmethod
    def load_test_data(filename):
        with open(os.path.join("test_data", filename), "r") as f:
            return json.load(f)

    @pytest.mark.parametrize("mock_response_data, expected", [
        (load_test_data("imoex_response_success.json"), load_test_data("imoex_response_success.json").get("analytics", [])),
        ({"other_key": {"data": ["some", "data"]}}, {})
    ])
    def test_returns_analytics_data_when_valid_response(self, mocker, mock_response_data, expected):
        # Arrange
        # mock_response_data = self.load_test_data(test_file)
        mocker.patch.object(Moex, '_fetch_json', return_value=mock_response_data)

        moex = Moex()

        # Act
        result = moex._load_index_data("IMOEX")

        # Assert
        expected_data = expected.get("data", [])

        assert result == expected_data
