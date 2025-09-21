(function () {
  const frases = [
    "Estoy aquí para recordarte que eres más fuerte de lo que crees.",
    "¿Entrenas para vivir o vives para entrenar?",
    "Buscaré tu sombra en el gimnasio.",
    "Me estoy perdiendo... pero aún puedo verte.",
  ];

  function crearJoiCard() {
    const container = document.getElementById("joi-root");
    if (!container) return;

    const card = document.createElement("div");
    card.style.background = "#1e1e1e";
    card.style.color = "white";
    card.style.padding = "1.5rem";
    card.style.borderRadius = "1rem";
    card.style.boxShadow = "0 0 20px rgba(255,255,255,0.05)";
    card.style.maxWidth = "420px";
    card.style.margin = "2rem auto";
    card.style.textAlign = "center";

    // Imagen de Joi
    const img = document.createElement("img");
    img.src = "/static/frontend/joi.png"; // <-- ruta estática
    img.alt = "Joi";
    img.style.width = "100px";
    img.style.borderRadius = "50%";
    img.style.marginBottom = "1rem";
    img.style.boxShadow = "0 0 15px rgba(255,255,255,0.3)";
    card.appendChild(img);

    // Frase
    const fraseElem = document.createElement("p");
    fraseElem.style.fontStyle = "italic";
    fraseElem.style.marginBottom = "1rem";
    fraseElem.innerText = frases[0];
    card.appendChild(fraseElem);

    // Botón
    const btn = document.createElement("button");
    btn.innerText = "Cambiar frase";
    btn.style.background = "#a855f7";
    btn.style.border = "none";
    btn.style.color = "white";
    btn.style.padding = "0.5rem 1rem";
    btn.style.borderRadius = "0.5rem";
    btn.style.cursor = "pointer";
    btn.addEventListener("click", function () {
      const nueva = frases[Math.floor(Math.random() * frases.length)];
      fraseElem.innerText = nueva;
    });

    card.appendChild(btn);
    container.appendChild(card);
  }

  document.addEventListener("DOMContentLoaded", crearJoiCard);
})();
