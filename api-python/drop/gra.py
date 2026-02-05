import matplotlib.pyplot as plt
from collections import Counter

def grafico_por_operadora(resultados):
    """
    resultados = lista de dicts (API) ou objetos PhoneInfo
    """

    operadoras = []

    for r in resultados:
        
        if isinstance(r, dict):
            if not r.get("valido", True):
                continue
            operadoras.append(r.get("operadora", "Desconhecida"))

        
        else:
            if not getattr(r, "valido", True):
                continue
            operadoras.append(getattr(r, "operadora", "Desconhecida"))

    if not operadoras:
        print("Nenhum dado válido para gerar gráfico.")
        return

    contagem = Counter(operadoras)

    nomes = list(contagem.keys())
    valores = list(contagem.values())

    plt.figure()
    plt.bar(nomes, valores)
    plt.title("Distribuição de Telefones por Operadora")
    plt.xlabel("Operadora")
    plt.ylabel("Quantidade")
    plt.show()
