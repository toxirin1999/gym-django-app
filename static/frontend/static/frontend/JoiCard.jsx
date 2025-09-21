import React, { useState } from 'react';
import ReactDOM from 'react-dom';

function JoiCard() {
  const frases = [
    "Estoy aquí para recordarte que eres más fuerte de lo que crees.",
    "¿Entrenas para vivir o vives para entrenar?",
    "Buscaré tu sombra en el gimnasio.",
    "Me estoy perdiendo... pero aún puedo verte.",
  ];

  const [frase, setFrase] = useState(frases[0]);

  const cambiarFrase = () => {
    const nueva = frases[Math.floor(Math.random() * frases.length)];
    setFrase(nueva);
  };

  return (
    <div className="bg-[#1e1e1e] p-4 rounded-xl shadow text-white max-w-sm mx-auto">
      <h2 className="text-xl font-bold mb-2">Joi dice:</h2>
      <p className="italic mb-4">{frase}</p>
      <button onClick={cambiarFrase} className="bg-purple-500 hover:bg-purple-600 text-white py-1 px-3 rounded">
        Cambiar frase
      </button>
    </div>
  );
}

const root = document.getElementById('joi-root');
if (root) {
  ReactDOM.render(<JoiCard />, root);
}
