"""
API client for wine cellar server communication.

Handles all HTTP communication with the Django server including:
- Wine CRUD operations
- Storage position updates
- Barcode lookups
- Offline operation syncing
"""

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


class APIError(Exception):
    """API request error."""

    def __init__(self, message: str, status_code: int = 0, response: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class ConnectionError(APIError):
    """Server connection error."""

    pass


@dataclass
class ServerConfig:
    """Server configuration."""

    host: str = "localhost"
    port: int = 8000
    use_https: bool = True
    api_prefix: str = "/api/v1"
    timeout: int = 30
    verify_ssl: bool = False  # Set False for self-signed certs
    username: str = ""
    password: str = ""
    token: str = ""


@dataclass
class Wine:
    """Wine data transfer object."""

    id: Optional[int] = None
    name: str = ""
    vintage: Optional[int] = None
    producer: str = ""
    region: str = ""
    country: str = ""
    grape_variety: str = ""
    barcode: str = ""
    notes: str = ""
    rating: Optional[float] = None
    price: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API."""
        data = {
            "name": self.name,
            "producer": self.producer,
            "region": self.region,
            "country": self.country,
            "grape_variety": self.grape_variety,
            "barcode": self.barcode,
            "notes": self.notes,
        }
        if self.id is not None:
            data["id"] = self.id
        if self.vintage is not None:
            data["vintage"] = self.vintage
        if self.rating is not None:
            data["rating"] = self.rating
        if self.price is not None:
            data["price"] = self.price
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Wine":
        """Create from API response."""
        return cls(
            id=data.get("id"),
            name=data.get("name", ""),
            vintage=data.get("vintage"),
            producer=data.get("producer", ""),
            region=data.get("region", ""),
            country=data.get("country", ""),
            grape_variety=data.get("grape_variety", ""),
            barcode=data.get("barcode", ""),
            notes=data.get("notes", ""),
            rating=data.get("rating"),
            price=data.get("price"),
        )


@dataclass
class StoragePosition:
    """Storage position data."""

    id: Optional[int] = None
    rack_id: int = 0
    row: int = 0
    col: int = 0
    wine_id: Optional[int] = None
    wine: Optional[Wine] = None
    is_empty: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rack_id": self.rack_id,
            "row": self.row,
            "col": self.col,
            "wine_id": self.wine_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoragePosition":
        wine_data = data.get("wine")
        return cls(
            id=data.get("id"),
            rack_id=data.get("rack_id", 0),
            row=data.get("row", 0),
            col=data.get("col", 0),
            wine_id=data.get("wine_id"),
            wine=Wine.from_dict(wine_data) if wine_data else None,
            is_empty=data.get("is_empty", True),
        )


class APIClient:
    """
    Client for wine cellar server API.

    Provides methods for all wine cellar operations that need
    to communicate with the Django server.
    """

    def __init__(self, config: Optional[ServerConfig] = None):
        """
        Initialize API client.

        Args:
            config: Server configuration, or None for defaults
        """
        self.config = config or ServerConfig()
        self._token = self.config.token
        self._ssl_context = self._create_ssl_context()

    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context for HTTPS."""
        if not self.config.verify_ssl:
            # Allow self-signed certificates
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return ctx
        return ssl.create_default_context()

    @property
    def base_url(self) -> str:
        """Get base URL for API requests."""
        protocol = "https" if self.config.use_https else "http"
        host = self.config.host
        port = self.config.port
        prefix = self.config.api_prefix
        return f"{protocol}://{host}:{port}{prefix}"

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        files: Optional[Dict[str, bytes]] = None,
    ) -> Dict[str, Any]:
        """
        Make HTTP request to server.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            data: Request body data
            files: Files to upload (name -> bytes)

        Returns:
            Response data as dictionary

        Raises:
            ConnectionError: If server is unreachable
            APIError: If request fails
        """
        url = f"{self.base_url}{endpoint}"

        headers = {
            "Accept": "application/json",
        }

        if self._token:
            headers["Authorization"] = f"Token {self._token}"

        body = None
        if files:
            # Multipart form data for file uploads
            boundary = "----WineCellarBoundary"
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
            body = self._encode_multipart(data or {}, files, boundary)
        elif data:
            headers["Content-Type"] = "application/json"
            body = json.dumps(data).encode("utf-8")

        request = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.config.timeout,
                context=self._ssl_context if self.config.use_https else None,
            ) as response:
                response_data = response.read().decode("utf-8")
                if response_data:
                    return json.loads(response_data)
                return {}

        except urllib.error.URLError as e:
            if isinstance(e.reason, (ConnectionRefusedError, OSError)):
                raise ConnectionError(f"Cannot connect to server: {e.reason}")
            raise APIError(f"Request failed: {e.reason}")

        except urllib.error.HTTPError as e:
            response_body = ""
            try:
                response_body = e.read().decode("utf-8")
            except Exception:
                pass
            raise APIError(
                f"HTTP {e.code}: {e.reason}", status_code=e.code, response=response_body
            )

        except json.JSONDecodeError as e:
            raise APIError(f"Invalid JSON response: {e}")

        except Exception as e:
            raise APIError(f"Request error: {e}")

    def _encode_multipart(
        self, data: Dict[str, Any], files: Dict[str, bytes], boundary: str
    ) -> bytes:
        """Encode multipart form data."""
        lines = []

        for key, value in data.items():
            lines.append(f"--{boundary}".encode())
            lines.append(f'Content-Disposition: form-data; name="{key}"'.encode())
            lines.append(b"")
            lines.append(str(value).encode())

        for name, content in files.items():
            lines.append(f"--{boundary}".encode())
            disposition = (
                f'Content-Disposition: form-data; name="{name}"; filename="{name}.jpg"'
            )
            lines.append(disposition.encode())
            lines.append(b"Content-Type: image/jpeg")
            lines.append(b"")
            lines.append(content)

        lines.append(f"--{boundary}--".encode())
        lines.append(b"")

        return b"\r\n".join(lines)

    def is_online(self) -> bool:
        """Check if server is reachable."""
        try:
            self._request("GET", "/health/")
            return True
        except ConnectionError:
            return False
        except APIError:
            # Server responded, even if with error
            return True

    def authenticate(self, username: str = "", password: str = "") -> bool:
        """
        Authenticate with server and get token.

        Args:
            username: Username (or use config)
            password: Password (or use config)

        Returns:
            True if authentication successful
        """
        username = username or self.config.username
        password = password or self.config.password

        try:
            response = self._request(
                "POST",
                "/auth/login/",
                {
                    "username": username,
                    "password": password,
                },
            )
            self._token = response.get("token", "")
            return bool(self._token)
        except APIError:
            return False

    # Wine operations

    def get_wine_by_barcode(self, barcode: str) -> Optional[Wine]:
        """
        Look up wine by barcode.

        Args:
            barcode: Barcode string

        Returns:
            Wine if found, None otherwise
        """
        try:
            response = self._request("GET", f"/wines/barcode/{barcode}/")
            return Wine.from_dict(response)
        except APIError as e:
            if e.status_code == 404:
                return None
            raise

    def get_wine(self, wine_id: int) -> Optional[Wine]:
        """Get wine by ID."""
        try:
            response = self._request("GET", f"/wines/{wine_id}/")
            return Wine.from_dict(response)
        except APIError as e:
            if e.status_code == 404:
                return None
            raise

    def create_wine(self, wine: Wine) -> Wine:
        """
        Create new wine entry.

        Args:
            wine: Wine data

        Returns:
            Created wine with ID
        """
        response = self._request("POST", "/wines/", wine.to_dict())
        return Wine.from_dict(response)

    def update_wine(self, wine: Wine) -> Wine:
        """Update existing wine."""
        if not wine.id:
            raise ValueError("Wine ID required for update")
        response = self._request("PUT", f"/wines/{wine.id}/", wine.to_dict())
        return Wine.from_dict(response)

    # Storage operations

    def get_rack_positions(self, rack_id: int) -> List[StoragePosition]:
        """Get all positions for a rack."""
        response = self._request("GET", f"/storage/racks/{rack_id}/positions/")
        return [StoragePosition.from_dict(p) for p in response.get("positions", [])]

    def get_position(
        self, rack_id: int, row: int, col: int
    ) -> Optional[StoragePosition]:
        """Get specific position."""
        try:
            response = self._request(
                "GET", f"/storage/racks/{rack_id}/positions/{row}/{col}/"
            )
            return StoragePosition.from_dict(response)
        except APIError as e:
            if e.status_code == 404:
                return None
            raise

    def add_wine_to_position(
        self, wine_id: int, rack_id: int, row: int, col: int
    ) -> StoragePosition:
        """
        Add wine to storage position.

        Args:
            wine_id: Wine ID
            rack_id: Rack ID
            row: Row number
            col: Column number

        Returns:
            Updated position
        """
        response = self._request(
            "POST",
            "/storage/add/",
            {
                "wine_id": wine_id,
                "rack_id": rack_id,
                "row": row,
                "col": col,
            },
        )
        return StoragePosition.from_dict(response)

    def remove_wine_from_position(
        self, rack_id: int, row: int, col: int
    ) -> Optional[Wine]:
        """
        Remove wine from storage position.

        Args:
            rack_id: Rack ID
            row: Row number
            col: Column number

        Returns:
            Removed wine, or None if position was empty
        """
        response = self._request(
            "POST",
            "/storage/remove/",
            {
                "rack_id": rack_id,
                "row": row,
                "col": col,
            },
        )
        wine_data = response.get("wine")
        return Wine.from_dict(wine_data) if wine_data else None

    # Hardware API endpoints (for Pi integration)

    def sync_operations(self, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Sync queued offline operations.

        Args:
            operations: List of operation dicts from offline queue

        Returns:
            Sync results
        """
        return self._request("POST", "/sync/", {"operations": operations})


def create_client(
    host: str = "localhost",
    port: int = 8000,
    use_https: bool = True,
    token: str = "",
) -> APIClient:
    """
    Create API client with common configuration.

    Args:
        host: Server hostname
        port: Server port
        use_https: Use HTTPS
        token: Authentication token

    Returns:
        Configured APIClient
    """
    config = ServerConfig(
        host=host,
        port=port,
        use_https=use_https,
        token=token,
    )
    return APIClient(config)
