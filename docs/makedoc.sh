#!/usr/bin/env bash

# set -ex

export NUM_RELEASES=2
export LATEST_JINA_VERSION='v2.4.7'
export DEFAULT_BRANCH='master'
export BUILD_DIR=_build/dirhtml

declare -a ARR_SMV_TAG_WHITELIST=()
declare -a ARR_SMV_BRANCH_WHITELIST=()

# rm -rf api && make clean
rm -rf api && rm -rf ${BUILD_DIR}

# API Limit exceeds
declare -a LAST_N_TAGS=( $(curl -s -H "Accept: application/vnd.github.v3+json" \
    "https://api.github.com/repos/jina-ai/jina/releases?per_page=${NUM_RELEASES}" \
    | jq -r '.[].tag_name') )
export LATEST_JINA_VERSION=${LAST_N_TAGS[1]}

if [[ $1 == "development" ]]; then
  current_branch=$(git branch --show-current)
  if [[ ${current_branch} != ${DEFAULT_BRANCH} ]]; then
    ARR_SMV_BRANCH_WHITELIST+=" ${current_branch}"
  fi


ARR_SMV_BRANCH_WHITELIST+=" ${DEFAULT_BRANCH}"
ARR_SMV_TAG_WHITELIST+=" ${LAST_N_TAGS[@]}"

docker run --rm \
  -v $(pwd)/proto:/out \
  -v $(pwd)/../jina/proto:/protos \
  pseudomuto/protoc-gen-doc --doc_opt=markdown,docs.md

export SMV_BRANCH_WHITELIST="${ARR_SMV_BRANCH_WHITELIST}"
export SMV_TAG_WHITELIST="${ARR_SMV_TAG_WHITELIST}"

echo $SMV_BRANCH_WHITELIST
echo $SMV_TAG_WHITELIST

sphinx-multiversion . ${BUILD_DIR}

cat >${BUILD_DIR}/index.html <<EOF
<!DOCTYPE html>
<html>
  <head>
    <title>Redirecting to latest</title>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="0; url=./${LATEST_JINA_VERSION}/index.html">
    # <link rel="canonical" href="https://username.github.io/reponame/master/index.html">
  </head>
</html>
EOF
