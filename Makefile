.PHONY: all install test clean lint mesh-example plan-example mesh-batch plan-batch all-batch

install:
	pip3 install -r requirements.txt

test:
	python3 -m pytest tests/ -v

clean:
	rm -rf examples/output/*
	rm -rf __pycache__ src/__pycache__ tests/__pycache__
	rm -rf .pytest_cache

lint:
	python3 -m py_compile src/string_art_utils.py
	python3 -m py_compile src/font_to_svg.py
	python3 -m py_compile src/svg_to_mesh_openscad.py
	python3 -m py_compile src/svg_to_nail_plan_svg.py

# Generate a quick example: letter J in Arial
OPENSCAD := $(shell command -v openscad 2>/dev/null || [ -x /Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD ] && echo "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD")

mesh-example:
	@mkdir -p examples/output
	python3 src/font_to_svg.py \
		--letter J \
		--font Arial \
		--output examples/output/letter_J.svg
	python3 src/svg_to_mesh_openscad.py \
		--input examples/output/letter_J.svg \
		--hole-diameter 5 \
		--wall-thickness 1 \
		--thickness 5 \
		--output examples/output/mesh_J.scad
	@if [ -n "$(OPENSCAD)" ]; then \
		echo "Rendering STL..."; \
		$(OPENSCAD) -o examples/output/mesh_J.stl examples/output/mesh_J.scad; \
		echo "STL saved to examples/output/mesh_J.stl"; \
	else \
		echo "Mesh example created (no OpenSCAD found for STL render)."; \
	fi
	@echo ""
	@echo "  SVG:  examples/output/letter_J.svg"
	@echo "  SCAD: examples/output/mesh_J.scad"
	@test -f examples/output/mesh_J.stl && echo "  STL:  examples/output/mesh_J.stl"

plan-example:
	@mkdir -p examples/output
	python3 src/font_to_svg.py \
		--letter A \
		--font Arial \
		--output examples/output/letter_A.svg
	python3 src/svg_to_nail_plan_svg.py \
		--input examples/output/letter_A.svg \
		--hole-diameter 3 \
		--output examples/output/plan_A.svg
	@echo ""
	@echo "  SVG:  examples/output/letter_A.svg"
	@echo "  Plan: examples/output/plan_A.svg"

# Batch generate all three — mesh SCAD, STL, and plan SVG (default: A-Z)
ALL_LETTERS ?= A B C D E F G H I J K L M N O P Q R S T U V W X Y Z
ARIAL_LETTERS ?= A B C D E F G H J L M N S T W Z
CGOTHIC_LETTERS ?= K Q
LUCIDA_LETTERS ?= I
CG_FONT_FILE ?=

gs-batch:
	@mkdir -p output
	python3 scripts/batch_generate.py --plan --letters $(ARIAL_LETTERS) --font "Arial" --no-outline
	python3 scripts/batch_generate.py --plan --letters $(CGOTHIC_LETTERS) --font-file "./internal/CenturyGothic.ttf" --no-outline
	python3 scripts/batch_generate.py --plan --letters $(LUCIDA_LETTERS) --font "Lucida Console" --no-outline

input-files:
	# Process input/ SVGs through the plan tool with --no-outline
	@for svg in input/*.svg; do \
		name=$$(basename "$$svg" .svg); \
		python3 src/svg_to_nail_plan_svg.py --input "$$svg" --output "output/plan_$$name.svg" --no-edges; \
	done


all-batch:
	@mkdir -p output
	python3 scripts/batch_generate.py --all --letters $(ALL_LETTERS)

# Batch generate just meshes (scad/stl)
mesh-batch:
	@mkdir -p output
	python3 scripts/batch_generate.py --mesh --letters $(ALL_LETTERS)

# Batch generate plan SVGs
plan-batch:
	@mkdir -p output
	python3 scripts/batch_generate.py --plan --letters $(ALL_LETTERS)
