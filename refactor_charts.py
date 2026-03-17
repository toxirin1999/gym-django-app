import os
import re
from bs4 import BeautifulSoup
import sys

# Color palettes based on LoL guidelines
COLORS = {
    'line_border': "'#C8AA6E'",
    'line_bg': "'rgba(200,170,110,0.08)'",
    'bar_bg': "'rgba(200,170,110,0.2)'",
    'bar_border': "'rgba(200,170,110,0.5)'",
    'radar_bg': "'rgba(200,170,110,0.1)'",
    'radar_border': "'#C8AA6E'",
    'gauge_optimo': "['#C8AA6E', 'rgba(200,170,110,0.1)']",
    'gauge_riesgo': "['#C84B31', 'rgba(200,75,49,0.1)']"
}

def fix_html_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Si no hay canvas, saltar
    if '<canvas' not in content:
        return False

    soup = BeautifulSoup(content, 'html.parser')
    canvases = soup.find_all('canvas')
    
    modified = False
    for canvas in canvases:
        # Check si ya está en un metric-card con el h4 del título insertado
        parent = canvas.find_parent('div', class_=lambda c: c and 'metric-card' in c)
        
        # O si justo antes hay un h4
        prev = canvas.find_previous_sibling()
        already_wrapped = parent and prev and prev.name == 'h4' and '◆' in prev.text
        
        if not already_wrapped:
            # Obtener ID para el título
            canvas_id = canvas.get('id', 'GRÁFICA')
            titulo = canvas_id.replace('Chart', '').replace('grafico', '').replace('ctx', '')
            titulo = titulo.upper() or 'ESTADÍSTICAS'

            # Crear el wrapper y el título usando reemplazo por regex puro para no ensuciar el templating de Django con bs4 formatter
            
            canvas_str = str(canvas)
            # Find the actual original string of the canvas in the document to preserve exact indentation
            # It's safer to just do a smart regex replacement
            
            # Simple wrapper injection
            wrapper = f'''<div class="metric-card bg-[var(--lol-bg-alt)] border border-[var(--lol-border-subtle)] p-4 rounded-sm shadow-xl relative overflow-hidden transition-all hover:border-[rgba(200,170,110,0.3)] hover:shadow-[0_0_15px_var(--lol-glow-gold)]">
    <h4 class="font-display text-[0.65rem] text-[var(--lol-gold-mid)] uppercase tracking-wider mb-3">◆ {titulo}</h4>
    {canvas_str}
</div>'''
            
            # Reemplazamos la ocurrencia exacta
            if canvas_str in content:
                content = content.replace(canvas_str, wrapper)
                modified = True

    if modified:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def fix_js_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'new Chart' not in content:
        return False
        
    original = content

    # REGLAS DE REEMPLAZO JS HARDCODEADO A DEFAULTS GLOBALES:
    # 1. Quitar configuraciones grid (estará en defaults)
    content = re.sub(r'grid:\s*\{\s*color:[^\}]+\}', '/* grid from defaults */', content)
    # 2. Quitar configuraciones ticks color/font hardcodeados (blanco o gris)
    content = re.sub(r'ticks:\s*\{\s*color:[^\}]+\}', '/* ticks from defaults */', content)
    
    # 3. Quitar la fuente de "legend: { labels: { color: 'white' } }" si existe explícitamente y bloquea los defaults
    content = re.sub(r'legend:\s*\{\s*labels:\s*\{\s*color:\s*[\'"][^\'"]+[\'"]\s*\}\s*\}', '/* legend defaults */', content)
    
    # 4. Injectar colores base según dataset type si se detectan:
    # type: 'line'
    content = re.sub(r"type:\s*['\"]line['\"],\s*data:\s*\{[\s\S]*?datasets:\s*\[\s*\{([\s\S]*?)borderColor:\s*['\"][^'\"]+['\"]([\s\S]*?)\}", 
                     r"type: 'line',\n    data: {\n        datasets: [{\1borderColor: " + COLORS['line_border'] + r"\2}", content)
    content = re.sub(r"type:\s*['\"]line['\"],\s*data:\s*\{[\s\S]*?datasets:\s*\[\s*\{([\s\S]*?)backgroundColor:\s*['\"][^'\"]+['\"]([\s\S]*?)\}", 
                     r"type: 'line',\n    data: {\n        datasets: [{\1backgroundColor: " + COLORS['line_bg'] + r"\2}", content)
    
    # type: 'bar'
    content = re.sub(r"type:\s*['\"]bar['\"],\s*data:\s*\{[\s\S]*?datasets:\s*\[\s*\{([\s\S]*?)borderColor:\s*['\"][^'\"]+['\"]([\s\S]*?)\}", 
                     r"type: 'bar',\n    data: {\n        datasets: [{\1borderColor: " + COLORS['bar_border'] + r"\2}", content)
    content = re.sub(r"type:\s*['\"]bar['\"],\s*data:\s*\{[\s\S]*?datasets:\s*\[\s*\{([\s\S]*?)backgroundColor:\s*['\"][^'\"]+['\"]([\s\S]*?)\}", 
                     r"type: 'bar',\n    data: {\n        datasets: [{\1backgroundColor: " + COLORS['bar_bg'] + r"\2}", content)

    # type: 'radar'
    content = re.sub(r"type:\s*['\"]radar['\"],\s*data:\s*\{[\s\S]*?datasets:\s*\[\s*\{([\s\S]*?)borderColor:\s*['\"][^'\"]+['\"]([\s\S]*?)\}", 
                     r"type: 'radar',\n    data: {\n        datasets: [{\1borderColor: " + COLORS['radar_border'] + r"\2}", content)
    content = re.sub(r"type:\s*['\"]radar['\"],\s*data:\s*\{[\s\S]*?datasets:\s*\[\s*\{([\s\S]*?)backgroundColor:\s*['\"][^'\"]+['\"]([\s\S]*?)\}", 
                     r"type: 'radar',\n    data: {\n        datasets: [{\1backgroundColor: " + COLORS['radar_bg'] + r"\2}", content)

    # type: 'doughnut' (usualmente gauges) -> Esto es más complejo hacer replace simple con regex así que lo dejaremos igual
    # O se aborda manualmente los gauges (Fatiga/ACWR)
    
    if content != original:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    root_dir = "/Users/davidmillanblanco/Desktop/app3/app/a/gymproject"
    modified_html = 0
    modified_js = 0
    
    for subdir, _, files in os.walk(root_dir):
        if 'site-packages' in subdir or 'node_modules' in subdir or '.git' in subdir:
            continue
            
        for file in files:
            path = os.path.join(subdir, file)
            if file.endswith('.html'):
                if fix_html_file(path):
                    modified_html += 1
                    print(f"[HTML] Modificado: {file}")
            elif file.endswith('.js'):
                if fix_js_file(path):
                    modified_js += 1
                    print(f"[JS] Modificado: {file}")
                    
    print(f"\\nProceso terminado. HTML Modificados: {modified_html}. JS Modificados: {modified_js}.")

if __name__ == "__main__":
    main()
