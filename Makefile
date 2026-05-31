.PHONY: all install test clean lint example plan-example batch batch-plan

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

# Generate a quick example: letter A in Arial
OPENSCAD := $(shell command -v openscad 2>/dev/null || [ -x /Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD ] && echo "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD")

mesh-example:
	@mkdir -p examples/output
	python3 src/font_to_svg.py \
		--letter A \
		--font Arial \
		--output examples/output/letter_A.svg
	python3 src/svg_to_mesh_openscad.py \
		--input examples/output/letter_A.svg \
		--spacing 10 \
		--hole-diameter 5 \
		--wall-thickness 1 \
		--thickness 5 \
		--corner-strategy 1 \
		--output examples/output/mesh_A.scad
	@if [ -n "$(OPENSCAD)" ]; then \
		echo "Rendering STL..."; \
		$(OPENSCAD) -o examples/output/mesh_A.stl examples/output/mesh_A.scad; \
		echo "STL saved to examples/output/mesh_A.stl"; \
	else \
		echo "Mesh example created (no OpenSCAD found for STL render)."; \
	fi
	@echo ""
	@echo "  SVG:  examples/output/letter_A.svg"
	@echo "  SCAD: examples/output/mesh_A.scad"
	@test -f examples/output/mesh_A.stl && echo "  STL:  examples/output/mesh_A.stl"

# Batch generate mesh models for a set of letters (default: A-Z)
LETTERS ?= A B C D E F G H I J K L M N O P Q R S T U V W X Y Z
mesh-batch:
	@mkdir -p output
	python3 scripts/batch_generate.py --mesh --letters $(LETTERS) --spacing 10 --hole-diameter 5 --wall-thickness 1

plan-example:
	@mkdir -p examples/output
	python3 src/font_to_svg.py \
		--letter A \
		--font Arial \
		--output examples/output/letter_A.svg
	python3 src/svg_to_nail_plan_svg.py \
		--input examples/output/letter_A.svg \
		--spacing 10 \
		--hole-diameter 3 \
		--corner-strategy 1 \
		--output examples/output/plan_A.svg
	@echo ""
	@echo "  SVG:  examples/output/letter_A.svg"
	@echo "  Plan: examples/output/plan_A.svg"

# Batch generate plan SVGs
plan-batch:
	@mkdir -p output
	python3 scripts/batch_generate.py --plan --letters $(LETTERS) --spacing 10 --hole-diameter 3
