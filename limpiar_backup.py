import json

with open('backup_completo_20260328_073034.json') as f:
    data = json.load(f)

seen = {}
cleaned = []
duplicates = 0

for obj in data:
    if obj['model'] == 'rutinas.ejerciciobase':
        nombre = obj['fields'].get('nombre', '')
        if nombre in seen:
            duplicates += 1
            print(f'Duplicado eliminado: {nombre} (pk={obj["pk"]})')
            continue
        seen[nombre] = obj['pk']
    cleaned.append(obj)

print(f'Total duplicados eliminados: {duplicates}')
print(f'Registros originales: {len(data)}, limpios: {len(cleaned)}')

with open('backup_limpio.json', 'w') as f:
    json.dump(cleaned, f)
print('Guardado: backup_limpio.json')
