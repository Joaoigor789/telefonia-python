const express = require("express");
const axios = require("axios");
const cors = require("cors");

const app = express();
app.use(express.json());
app.use(cors());


const PYTHON_API = process.env.PYTHON_API || "http://api-python:8000";

app.get("/", (req, res) => {
  res.json({
    status: "Node API online",
    python_api: PYTHON_API
  });
});

app.post("/telefone", async (req, res) => {
  try {
    const { numero } = req.body;

    if (!numero) {
      return res.status(400).json({ erro: "Número é obrigatório" });
    }

    const response = await axios.get(
      `${PYTHON_API}/consulta`,
      { params: { numero } }
    );

    res.json(response.data);
  } catch (err) {
    res.status(500).json({
      erro: "Erro ao consultar telefone",
      detalhe: err.response?.data || err.message
    });
  }
});

app.post("/telefone/lote", async (req, res) => {
  try {
    if (!Array.isArray(req.body)) {
      return res.status(400).json({
        erro: "Envie um array de números"
      });
    }

    const response = await axios.post(
      `${PYTHON_API}/consulta/lote`,
      req.body
    );

    res.json(response.data);
  } catch (err) {
    res.status(500).json({
      erro: "Erro na consulta em lote",
      detalhe: err.response?.data || err.message
    });
  }
});

app.listen(3000, () => {
  console.log(" Node API rodando na porta 3000");
  console.log(" Conectando na API Python:", PYTHON_API);
});
