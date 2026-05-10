import time


class RequestLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        response = self.get_response(request)
        elapsed_ms = (time.time() - start_time) * 1000
        print(f"{request.method} {request.path} completed in {elapsed_ms:.2f}ms")
        return response
