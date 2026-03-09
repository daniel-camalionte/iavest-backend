from model.Etapa import EtapaModel
from model.EtapaSub import EtapaSubModel

class EtapaRule():

    def listar(self):
        modEtapa = EtapaModel()
        etapas = modEtapa.order('ordem', 'ASC').find()

        if not etapas:
            return {"success": True, "etapas": []}, 200

        modSub = EtapaSubModel()
        lista = []
        for etapa in etapas:
            subs = modSub.where(["id_etapa", "=", etapa["id_etapa"]]).order('ordem', 'ASC').find()

            sub_lista = []
            if subs:
                for sub in subs:
                    sub_lista.append({
                        "id_etapa_sub": sub["id_etapa_sub"],
                        "ordem": sub["ordem"],
                        "titulo": sub["titulo"],
                        "descricao": sub["descricao"],
                        "url": sub["url"],
                        "video": sub["video"]
                    })

            lista.append({
                "id_etapa": etapa["id_etapa"],
                "ordem": etapa["ordem"],
                "titulo": etapa["titulo"],
                "descricao": etapa["descricao"],
                "url": etapa["url"],
                "video": etapa["video"],
                "sub_etapas": sub_lista
            })

        return {"success": True, "etapas": lista}, 200
