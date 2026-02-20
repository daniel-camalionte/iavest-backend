from flask import g, request

def requer_header(f):
    def funcao_decorada():
        header = request.headers.get('Authorization')
        if header:
            f()
    return funcao_decorada