import time
from model.Faq import FaqModel

_CACHE_TTL = 60 * 60 * 24 * 30  # 30 dias
_cache     = {"data": None, "timestamp": None}


class FaqRule:

    @staticmethod
    def listar():
        now = time.time()
        if _cache["data"] and _cache["timestamp"] and (now - _cache["timestamp"]) < _CACHE_TTL:
            return {"success": True, "cached": True, "faqs": _cache["data"]}, 200

        faqs = FaqModel().where(['ativo', '=', 1]).order('ordem', 'ASC').find() or []

        lista = []
        for f in faqs:
            lista.append({
                "id":       f["id_faq"],
                "pergunta": f["pergunta"],
                "resposta": f["resposta"],
                "video":    f["video"] or None,
                "url":      f["url"] or None,
            })

        _cache["data"]      = lista
        _cache["timestamp"] = now

        return {"success": True, "cached": False, "faqs": lista}, 200

    @staticmethod
    def clear_cache():
        _cache["data"]      = None
        _cache["timestamp"] = None
        return {"success": True, "message": "Cache limpo com sucesso"}, 200
