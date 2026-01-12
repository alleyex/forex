"""
OAuth Token 交換工具
"""
import json
import time
import urllib.parse
import urllib.request
from typing import Optional

from config.settings import OAuthTokens, AppCredentials


class TokenExchanger:
    """
    處理 OAuth Token 交換操作
    
    負責：
    - 建構授權 URL
    - 將授權碼交換為 Token
    """
    
    TOKEN_URL = "https://openapi.ctrader.com/apps/token"
    AUTH_URL = "https://openapi.ctrader.com/apps/auth"
    
    def __init__(self, credentials: AppCredentials, redirect_uri: str):
        self._credentials = credentials
        self._redirect_uri = redirect_uri
    
    def build_authorize_url(self) -> str:
        """建構 OAuth 授權 URL"""
        params = {
            "client_id": self._credentials.client_id,
            "redirect_uri": self._redirect_uri,
            "scope": "trading",
        }
        return f"{self.AUTH_URL}?{urllib.parse.urlencode(params)}"
    
    def exchange_code(
        self, 
        code: str, 
        existing_account_id: Optional[int] = None
    ) -> OAuthTokens:
        """
        將授權碼交換為 Token
        
        Args:
            code: 授權碼
            existing_account_id: 現有的帳戶 ID（可選，用於保留）
            
        Returns:
            OAuthTokens 實例
            
        Raises:
            RuntimeError: Token 交換失敗
        """
        data = {
            "grant_type": "authorization_code",
            "client_id": self._credentials.client_id,
            "client_secret": self._credentials.client_secret,
            "code": code,
            "redirect_uri": self._redirect_uri,
        }
        
        response = self._post_request(data)
        return self._parse_token_response(response, existing_account_id)
    
    def _post_request(self, data: dict) -> dict:
        """發送 POST 請求並回傳解析後的 JSON 回應"""
        encoded = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(self.TOKEN_URL, data=encoded, method="POST")
        
        with urllib.request.urlopen(req, timeout=15) as response:
            payload = response.read().decode("utf-8")
        
        return self._safe_json_loads(payload)
    
    def _parse_token_response(
        self, 
        parsed: dict, 
        existing_account_id: Optional[int]
    ) -> OAuthTokens:
        """解析 Token 回應"""
        if "error" in parsed:
            raise RuntimeError(parsed.get("error_description") or parsed["error"])
        
        expires_in = parsed.get("expires_in")
        expires_at = int(time.time()) + expires_in if isinstance(expires_in, int) else None
        
        return OAuthTokens(
            access_token=parsed.get("access_token", ""),
            refresh_token=parsed.get("refresh_token", ""),
            expires_at=expires_at,
            account_id=existing_account_id,
        )
    
    @staticmethod
    def _safe_json_loads(payload: str) -> dict:
        """安全地解析 JSON"""
        try:
            return json.loads(payload)
        except Exception as e:
            raise RuntimeError(f"無效的 Token 回應: {e}")