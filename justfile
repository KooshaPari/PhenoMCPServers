# PhenoMCPServers — Build system alias (just = make replacement)
set dotenv-load

# default: list recipes
default:
    @just --list

# install
install:
    @echo "TODO: install PhenoMCPServers deps"

# build
build:
    @echo "TODO: build PhenoMCPServers"

# test
test:
    @echo "TODO: test PhenoMCPServers"

# lint
lint:
    @echo "TODO: lint PhenoMCPServers"

# format
format:
    @echo "TODO: format PhenoMCPServers"

# verify (justfile-verify-in-pre-commit hook gate)
verify:
    @just --evaluate
