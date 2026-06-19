from library.base.BaseModel import BaseModel


class SimuladorOrdemClienteModel(BaseModel):

    def __init__(self):
        super().__init__()

    def table(self):
        return 'simulador_ordem_cliente'

    def pk(self):
        return 'id_ordem_cliente'

    def fields(self):
        return {
            "id_ordem_cliente":   "id_ordem_cliente",
            "id_cliente":         "id_cliente",
            "executada_em":       "executada_em",
            "id_ativos_base":     "id_ativos_base",
            "id_market_analysis": "id_market_analysis",

            "direcao":            "direcao",
            "contratos":          "contratos",
            "preco_entrada":      "preco_entrada",
            "stop_loss":          "stop_loss",
            "alvo":               "alvo",

            "status":             "status",
            "resultado":          "resultado",
            "resultado_pontos":   "resultado_pontos",
            "preco_saida":        "preco_saida",
            "encerrada_em":       "encerrada_em",

            "created_at":         "created_at",
        }
