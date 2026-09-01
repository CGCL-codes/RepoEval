git clone https://github.com/google/oss-fuzz.git

OSSFUZZ_DIR=$(pwd)/oss-fuzz
cd $OSSFUZZ_DIR

# Build the fuzzers.

DEFAULT_PROJECTS=("jansson" "cpp-httplib" "sqlite3" "exiv2" "jedis" "jsoup" "async-http-client" "metadata-extractor")
for project in "${DEFAULT_PROJECTS[@]}"; do
  python infra/helper.py build_fuzzers --sanitizer coverage $project --clean
done
