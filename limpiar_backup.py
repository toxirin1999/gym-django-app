import json

with open('backup_completo_20260328_073034.json') as f:
    data = json.load(f)

seen = {}
cleaned = []
duplicates = 0

for obj in data:
    if obj['model'] == 'rutinas.ejerciciobase':
        # Case-insensitive + strip para que MySQL (utf8mb4_unicode_ci) no rechace
        nombre_key = obj['fields'].get('nombre', '').strip().lower()
        if nombre_key in seen:
            duplicates += 1
            print(f'Duplicado eliminado: pk={obj["pk"]} nombre="{obj["fields"]["nombre"]}" (igual a pk={seen[nombre_key]})')
            continue
        seen[nombre_key] = obj['pk']
    cleaned.append(obj)

print(f'Total duplicados eliminados: {duplicates}')
print(f'Registros originales: {len(data)}, limpios: {len(cleaned)}')

with open('backup_limpio.json', 'w') as f:
    json.dump(cleaned, f)
print('Guardado: backup_limpio.json')
