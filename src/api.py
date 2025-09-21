from flask import Flask, request, jsonify
# Importamos la clase Usuario de tu código existente
from .usuario import Usuario

# 1. Inicializamos la aplicación Flask
app = Flask(__name__)

# Definimos la ruta al archivo de usuarios para no repetirla
RUTA_USUARIOS = '../data/usuarios.json'


# 2. Creamos nuestro primer "endpoint"
# Este endpoint responderá a peticiones POST en la URL /api/login
@app.route('/api/login', methods=['POST'])
def login():
    """
    Endpoint para iniciar sesión.
    Espera un JSON con la clave "nombre".
    Ej: {"nombre": "toxirin"}
    """
    print("¡Se ha recibido una petición en /api/login!")

    # 3. Obtenemos los datos que nos envía el cliente
    # Ya no usamos input(), sino que leemos el JSON de la petición
    datos = request.get_json()
    if not datos or 'nombre' not in datos:
        return jsonify({"error": "Falta el campo 'nombre' en la petición"}), 400

    nombre_usuario = datos['nombre']
    print(f"Intentando iniciar sesión para el usuario: {nombre_usuario}")

    # 4. Reutilizamos TU lógica original para buscar al usuario
    try:
        usuarios = Usuario.cargar_usuarios(RUTA_USUARIOS)
        usuario_encontrado = None
        for u in usuarios:
            if u.nombre.lower() == nombre_usuario.lower():
                usuario_encontrado = u
                break
    except FileNotFoundError:
        return jsonify({"error": "No se encontró el archivo de usuarios."}), 500

    # 5. Devolvemos una respuesta en formato JSON
    if usuario_encontrado:
        print(f"Usuario '{nombre_usuario}' encontrado. Devolviendo datos.")
        # Convertimos el objeto usuario a un diccionario para poder enviarlo como JSON
        datos_usuario = {
            "nombre": usuario_encontrado.nombre,
            "edad": usuario_encontrado.edad,
            "peso": usuario_encontrado.peso,
            "altura": usuario_encontrado.altura
        }
        return jsonify({
            "mensaje": "Inicio de sesión exitoso",
            "usuario": datos_usuario
        }), 200  # Código 200: OK
    else:
        print(f"Usuario '{nombre_usuario}' no encontrado.")
        return jsonify({"error": "Usuario no encontrado"}), 404  # Código 404: Not Found


# Esta parte permite ejecutar el servidor directamente desde la terminal
if __name__ == '__main__':
    # El host='0.0.0.0' permite que sea accesible desde otros dispositivos en tu red
    # El debug=True hace que el servidor se reinicie solo cuando guardas cambios
    app.run(host='0.0.0.0', port=5000, debug=True)
