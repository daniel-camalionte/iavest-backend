#!/bin/bash
# install.sh - Instala os hooks git para exportação automática de commits
#
# Execute uma vez após clonar o repositório:
#   bash hooks/install.sh

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOKS_SRC="${REPO_ROOT}/hooks"
HOOKS_DST="${REPO_ROOT}/.git/hooks"

echo "Instalando hooks de exportação de commits..."

cp "${HOOKS_SRC}/_export_commit.sh" "${HOOKS_DST}/_export_commit.sh"
cp "${HOOKS_SRC}/post-commit"       "${HOOKS_DST}/post-commit"
cp "${HOOKS_SRC}/post-merge"        "${HOOKS_DST}/post-merge"

chmod +x "${HOOKS_DST}/_export_commit.sh"
chmod +x "${HOOKS_DST}/post-commit"
chmod +x "${HOOKS_DST}/post-merge"

echo "Hooks instalados com sucesso em: ${HOOKS_DST}"
echo ""
echo "Hooks ativos:"
echo "  post-commit  -> exporta arquivos após cada commit (branches: stg, master)"
echo "  post-merge   -> exporta arquivos após cada merge  (branches: stg, master)"
echo ""
echo "Destinos de exportação:"
echo "  stg    -> /c/GIT/iavest/commit/stg"
echo "  master -> /c/GIT/iavest/commit/master"
