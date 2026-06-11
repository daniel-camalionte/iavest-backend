from flask.views import MethodView
from rule.Faq import FaqRule


class FaqListController(MethodView):

    def get(self):
        return FaqRule.listar()


class FaqCacheClearController(MethodView):

    def delete(self):
        return FaqRule.clear_cache()
