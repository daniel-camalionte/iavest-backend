from model.Etapa import EtapaModel

class EtapaRule():

    def listar(self):
        modEtapa = EtapaModel()
        etapas = modEtapa.order('ordem', 'ASC').find()

        if not etapas:
            return {"success": True, "etapas": []}, 200

        lista = []
        for etapa in etapas:
            lista.append({
                "id_etapa": etapa["id_etapa"],
                "ordem": etapa["ordem"],
                "titulo": etapa["titulo"],
                "descricao": etapa["descricao"],
                "url": etapa["url"],
                "video": etapa["video"]
            })

        return {"success": True, "etapas": lista}, 200
