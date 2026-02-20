import urllib.request
import json
import ssl

class HttpClient():

    @staticmethod
    def _request(method, url, headers=None, payload=None, timeout=30):
        data = json.dumps(payload).encode('utf-8') if payload else None
        req = urllib.request.Request(url, data=data, method=method)

        if headers:
            for key, value in headers.items():
                req.add_header(key, value)

        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            ctx = ssl.create_default_context()

        try:
            response = urllib.request.urlopen(req, timeout=timeout, context=ctx)
            body = response.read().decode('utf-8')
            return {"status_code": response.status, "data": json.loads(body)}
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8') if e.fp else ''
            try:
                resp_data = json.loads(body)
            except:
                resp_data = {"error": body}
            return {"status_code": e.code, "data": resp_data}
        except Exception as e:
            return {"status_code": 0, "data": {"error": str(e)}}

    @staticmethod
    def post(url, headers=None, payload=None, timeout=30):
        return HttpClient._request('POST', url, headers, payload, timeout)

    @staticmethod
    def put(url, headers=None, payload=None, timeout=30):
        return HttpClient._request('PUT', url, headers, payload, timeout)

    @staticmethod
    def get(url, headers=None, timeout=30):
        return HttpClient._request('GET', url, headers, timeout=timeout)
