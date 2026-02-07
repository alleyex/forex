"""
OAuth 回調伺服器
"""
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional, Tuple, Callable
from urllib import parse


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """OAuth 回調的 HTTP 處理器"""
    
    def do_GET(self):
        """處理 GET 請求"""
        parsed = parse.urlparse(self.path)
        params = parse.parse_qs(parsed.query)
        self.server.code = params.get("code", [None])[0]
        self.server.request_path = parsed.path
        
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("授權完成，您可以關閉此視窗。".encode("utf-8"))

    def log_message(self, format, *args):
        """抑制日誌輸出"""
        pass


class CallbackServer:
    """
    接收 OAuth 回調的本地伺服器
    
    負責：
    - 啟動本地 HTTP 伺服器
    - 開啟瀏覽器進行授權
    - 等待並接收授權碼
    """
    
    DEFAULT_TIMEOUT = 300  # 5 分鐘
    
    def __init__(self, redirect_uri: str):
        self._host, self._port, self._path = self._parse_uri(redirect_uri)
    
    @staticmethod
    def _parse_uri(redirect_uri: str) -> Tuple[str, int, str]:
        """
        解析重導向 URI
        
        Args:
            redirect_uri: 完整的重導向 URI
            
        Returns:
            (host, port, path) 元組
            
        Raises:
            ValueError: URI 格式無效
        """
        parsed = parse.urlparse(redirect_uri)
        host = parsed.hostname
        port = parsed.port
        path = parsed.path or "/"
        
        if not host or not port:
            raise ValueError("無效的重導向 URI，需要主機和埠號")
        return host, port, path
    
    def wait_for_code(
        self, 
        auth_url: str, 
        timeout_seconds: int = DEFAULT_TIMEOUT,
        on_log: Optional[Callable[[str], None]] = None
    ) -> Optional[str]:
        """
        等待 OAuth 授權碼
        
        Args:
            auth_url: 授權 URL
            timeout_seconds: 逾時秒數
            on_log: 日誌回調函式
            
        Returns:
            授權碼，若逾時則回傳 None
        """
        try:
            server = self._create_server()
        except OSError as exc:
            if on_log:
                on_log(f"⚠️ 無法啟動回調伺服器，可能是埠被占用: {exc}")
                on_log("ℹ️ 可改用手動貼上授權碼流程")
            return None
        
        if on_log:
            on_log("🌐 正在開啟瀏覽器進行 OAuth 授權...")
        webbrowser.open(auth_url)
        
        return self._wait_for_callback(server, timeout_seconds)
    
    def _create_server(self) -> HTTPServer:
        """建立並設定 HTTP 伺服器"""
        server = HTTPServer((self._host, self._port), OAuthCallbackHandler)
        server.code = None
        server.request_path = None
        server.timeout = 1
        return server
    
    def _wait_for_callback(
        self, 
        server: HTTPServer, 
        timeout_seconds: int
    ) -> Optional[str]:
        """等待回調並回傳授權碼"""
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            server.handle_request()
            if server.code:
                # 驗證路徑是否匹配
                if self._path and server.request_path:
                    if server.request_path != self._path:
                        continue
                return server.code
        
        return None
