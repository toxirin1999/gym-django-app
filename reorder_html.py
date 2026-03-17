import os
import re

file_path = "entrenos/templates/entrenos/vista_plan_calendario.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# We need to extract:
# 1. The Objectives container start and end
# 2. The Phase panels layout 
# 3. The Calendar sections

# Extract Calendar Blocks
calendar_pattern = re.compile(r'(    <!-- SELECTOR DE MES -->.*?<!-- LEYENDA DE FASES -->.*?</div>\n)', re.DOTALL)
calendar_match = calendar_pattern.search(content)
calendar_code = calendar_match.group(1) if calendar_match else ""

# Extract Phase Panels Layout
phase_panels_pattern = re.compile(r'(            <!-- PHASE INFO PANELS REDESIGN -->.*?</svg>\n.*?</div>\n.*?</div>\n.*?</div>\n.*?</div>\n)', re.DOTALL)
phase_panels_match = phase_panels_pattern.search(content)
phase_panels_code = phase_panels_match.group(1) if phase_panels_match else ""

# Extract Objectives Container (without Phase Panels layout)
objectives_pattern = re.compile(r'(    <!-- Contenedor Principal de Fases y Proyecciones -->\n    <div id="projections-container" class="proj-panel"\n        style="display: {% if fase_actual %}block{% else %}none{% endif %};">.*?        </div>\n)', re.DOTALL)
objectives_match = objectives_pattern.search(content)

if objectives_match and "<!-- PHASE INFO PANELS REDESIGN -->" in objectives_match.group(1):
    # Wait, the objectives pattern regex needs to match JUST the start up to the phase panels.
    pass

# Better approach using string splitting with known unique markers.

mark_proj_start = "    <!-- Contenedor Principal de Fases y Proyecciones -->"
mark_phase_panels_start = "            <!-- PHASE INFO PANELS REDESIGN -->"
mark_calendar_start = "    <!-- SELECTOR DE MES -->"
mark_main_start = "    <!-- CONTENIDO PRINCIPAL -->"

# Part 1: before projections
part1 = content.split(mark_proj_start)[0]
rest = mark_proj_start + content.split(mark_proj_start)[1]

# Part 2: projections top (Objectives)
objectives_top = rest.split(mark_phase_panels_start)[0]
rest2 = mark_phase_panels_start + rest.split(mark_phase_panels_start)[1]

# Part 3: Phase panels
phase_panels = rest2.split(mark_calendar_start)[0]
rest3 = mark_calendar_start + rest2.split(mark_calendar_start)[1]

# Note: phase_panels currently includes the closing divs for projections-container.
# Let's clean that up. phase_panels ends with </div>\n\n        </div>\n    </div>\n
phase_panels_clean = phase_panels.rsplit("        </div>\n    </div>\n", 1)[0]
# Add the closing divs to the objectives top to make it a complete block
objectives_complete = objectives_top + "    </div>\n"

# Part 4: Calendar
calendar = rest3.split(mark_main_start)[0]
# Part 5: the rest (main content)
part5 = mark_main_start + rest3.split(mark_main_start)[1]

# Reassemble in the new order:
# Calendar -> Phase Panels -> Objectives Complete

new_content = part1 + calendar + "\n" + phase_panels_clean + "\n" + objectives_complete + "\n" + part5

with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("HTML reordering applied successfully.")
