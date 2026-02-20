#!/bin/bash
# _export_commit.sh - Lógica compartilhada de exportação de commits
# Chamado por post-commit e post-merge
#
# Uso: source _export_commit.sh <commit_hash> <files_list>
#   ou chamar export_commit <commit_hash> <files_newline_separated>

export_commit() {
    local COMMIT_HASH="$1"
    local FILES="$2"

    # Verifica se há arquivos para exportar
    if [ -z "$FILES" ]; then
        echo "[export] Nenhum arquivo para exportar no commit ${COMMIT_HASH}."
        return 0
    fi

    # Branch atual
    local BRANCH
    BRANCH=$(git rev-parse --abbrev-ref HEAD)

    # Só processa stg e master
    if [ "$BRANCH" != "stg" ] && [ "$BRANCH" != "master" ]; then
        echo "[export] Branch '${BRANCH}' não configurada para exportação. Pulando."
        return 0
    fi

    # Diretório destino por branch
    local TARGET_BASE
    if [ "$BRANCH" = "stg" ]; then
        TARGET_BASE="/c/GIT/iavest/commit/stg"
    else
        TARGET_BASE="/c/GIT/iavest/commit/master"
    fi

    # Metadados do commit
    local DATE
    DATE=$(date +"%Y%m%d")
    local DATETIME
    DATETIME=$(date +"%d/%m/%Y %H:%M:%S")
    local COMMIT_MSG
    COMMIT_MSG=$(git log -1 --pretty="%B" "$COMMIT_HASH")
    local COMMIT_AUTHOR
    COMMIT_AUTHOR=$(git log -1 --pretty="%an <%ae>" "$COMMIT_HASH")

    # Pasta destino: AAAAMMDD-hash
    local FOLDER="${TARGET_BASE}/${DATE}-${COMMIT_HASH}"
    mkdir -p "$FOLDER"

    # Copia arquivos preservando estrutura de diretórios
    local COPIED=()
    local MISSING=()

    while IFS= read -r FILE; do
        [ -z "$FILE" ] && continue
        if [ -f "$FILE" ]; then
            local DEST_DIR
            DEST_DIR=$(dirname "${FOLDER}/${FILE}")
            mkdir -p "$DEST_DIR"
            cp "$FILE" "${FOLDER}/${FILE}"
            COPIED+=("$FILE")
        else
            # Arquivo removido no commit (deletado)
            MISSING+=("$FILE (removido)")
        fi
    done <<< "$FILES"

    # Monta lista formatada de arquivos
    local FILES_COPIED_LIST=""
    for f in "${COPIED[@]}"; do
        FILES_COPIED_LIST+="  [COPIADO]  ${f}"$'\n'
    done
    for f in "${MISSING[@]}"; do
        FILES_COPIED_LIST+="  [REMOVIDO] ${f}"$'\n'
    done

    # Cria arquivo de descrição
    cat > "${FOLDER}/ALTERACOES.txt" << EOF
==========================================
 EXPORTACAO DE COMMIT
==========================================
 Commit  : ${COMMIT_HASH}
 Data    : ${DATETIME}
 Branch  : ${BRANCH}
 Autor   : ${COMMIT_AUTHOR}
==========================================

 MENSAGEM DO COMMIT:
------------------------------------------
${COMMIT_MSG}
==========================================

 ARQUIVOS ALTERADOS:
------------------------------------------
${FILES_COPIED_LIST}
==========================================
EOF

    echo "[export] Commit ${COMMIT_HASH} exportado para: ${FOLDER}"
    echo "[export] ${#COPIED[@]} arquivo(s) copiado(s), ${#MISSING[@]} removido(s)."
}
