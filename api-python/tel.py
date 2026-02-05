
import re
import requests
import json
import sys
import os
import csv
import time
import hashlib
import argparse
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from pathlib import Path
from tabulate import tabulate


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


CACHE_DIR = Path.home() / ".cache/fone"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL = 86400  
OCEL_KEY = "test"  
MCC = 724  

@dataclass
class PhoneInfo:
    """Estrutura para informações do telefone"""
    numero: str
    ddd: str
    prefixo: str
    sufixo: str
    operadora: str = "Desconhecida"
    cidade: str = "Desconhecida"
    uf: str = "??"
    tipo: str = "Desconhecido"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    consulta_ts: int = 0
    valido: bool = False
    portabilidade: bool = False
    
    def formatado(self) -> str:
        """Retorna número formatado"""
        if self.tipo == "MÓVEL":
            return f"({self.ddd}) 9{self.prefixo}-{self.sufixo}"
        else:
            return f"({self.ddd}) {self.prefixo}-{self.sufixo}"

class PhoneValidator:
    """Validador e normalizador de números de telefone brasileiros"""
    
    
    PATTERNS = {
        'mobile': r'^(\d{2})(9\d{4})(\d{4})$',  
        'landline': r'^(\d{2})([2-5]\d{3})(\d{4})$',  
        'short': r'^(\d{2})([2-5]\d{2})(\d{4})$',  
    }
    
    @staticmethod
    def normalize(phone: str) -> Optional[str]:
        """Remove todos os não-dígitos e normaliza"""
        digits = re.sub(r'\D', '', phone)
        
    
        if len(digits) == 11 and digits[0] == '0':
            digits = digits[1:]
        
        return digits if 10 <= len(digits) <= 11 else None
    
    @staticmethod
    def validate(phone: str) -> Tuple[bool, str, Dict[str, str]]:
        """Valida e retorna informações do número"""
        digits = PhoneValidator.normalize(phone)
        if not digits:
            return False, "Formato inválido", {}
        
    
        if len(digits) == 11 and digits[2] == '9':
            match = re.match(PhoneValidator.PATTERNS['mobile'], digits)
            if match:
                return True, "MÓVEL", {
                    'ddd': match.group(1),
                    'prefixo': match.group(2)[1:], 
                    'sufixo': match.group(3),
                    'raw_prefixo': match.group(2)
                }
        
        
        elif len(digits) == 11:
            match = re.match(PhoneValidator.PATTERNS['landline'], digits)
            if match:
                return True, "FIXO", {
                    'ddd': match.group(1),
                    'prefixo': match.group(2),
                    'sufixo': match.group(3)
                }
        
        
        elif len(digits) == 10:
            match = re.match(PhoneValidator.PATTERNS['short'], digits)
            if match:
                return True, "FIXO", {
                    'ddd': match.group(1),
                    'prefixo': match.group(2),
                    'sufixo': match.group(3)
                }
        
        return False, "Formato não reconhecido", {}

class CacheManager:
    """Gerenciador de cache com TTL"""
    
    @staticmethod
    def get_key(phone: str) -> str:
        """Gera chave de cache"""
        return hashlib.md5(phone.encode()).hexdigest()
    
    @staticmethod
    def load(phone: str) -> Optional[Dict]:
        """Carrega dados do cache se não expirados"""
        cache_file = CACHE_DIR / f"{CacheManager.get_key(phone)}.json"
        
        if not cache_file.exists():
            return None
        
        try:
            with cache_file.open() as f:
                data = json.load(f)
            
        
            if time.time() - data.get('consulta_ts', 0) > CACHE_TTL:
                cache_file.unlink()  
                return None
            
            return data
        except Exception as e:
            logger.warning(f"Erro ao ler cache: {e}")
            return None
    
    @staticmethod
    def save(phone: str, data: Dict):
        """Salva dados no cache"""
        cache_file = CACHE_DIR / f"{CacheManager.get_key(phone)}.json"
        
        try:
            with cache_file.open('w') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Erro ao salvar cache: {e}")

class PhoneLookup:
    """Serviço de consulta de telefones"""
    
    
    DDD_DATABASE = {
        "11": {"estado": "SP", "regiao": "São Paulo/SP"},
        "12": {"estado": "SP", "regiao": "São José dos Campos/SP"},
        "13": {"estado": "SP", "regiao": "Santos/SP"},
        "14": {"estado": "SP", "regiao": "Bauru/SP"},
        "15": {"estado": "SP", "regiao": "Sorocaba/SP"},
        "16": {"estado": "SP", "regiao": "Ribeirão Preto/SP"},
        "17": {"estado": "SP", "regiao": "São José do Rio Preto/SP"},
        "18": {"estado": "SP", "regiao": "Presidente Prudente/SP"},
        "19": {"estado": "SP", "regiao": "Campinas/SP"},
        "21": {"estado": "RJ", "regiao": "Rio de Janeiro/RJ"},
        "22": {"estado": "RJ", "regiao": "Campos dos Goytacazes/RJ"},
        "24": {"estado": "RJ", "regiao": "Volta Redonda/RJ"},
        "27": {"estado": "ES", "regiao": "Vitória/ES"},
        "28": {"estado": "ES", "regiao": "Cachoeiro de Itapemirim/ES"},
        "31": {"estado": "MG", "regiao": "Belo Horizonte/MG"},
        "32": {"estado": "MG", "regiao": "Juiz de Fora/MG"},
        "33": {"estado": "MG", "regiao": "Governador Valadares/MG"},
        "34": {"estado": "MG", "regiao": "Uberlândia/MG"},
        "35": {"estado": "MG", "regiao": "Poços de Caldas/MG"},
        "37": {"estado": "MG", "regiao": "Divinópolis/MG"},
        "38": {"estado": "MG", "regiao": "Montes Claros/MG"},
        "41": {"estado": "PR", "regiao": "Curitiba/PR"},
        "42": {"estado": "PR", "regiao": "Ponta Grossa/PR"},
        "43": {"estado": "PR", "regiao": "Londrina/PR"},
        "44": {"estado": "PR", "regiao": "Maringá/PR"},
        "45": {"estado": "PR", "regiao": "Foz do Iguaçu/PR"},
        "46": {"estado": "PR", "regiao": "Francisco Beltrão/PR"},
        "47": {"estado": "SC", "regiao": "Joinville/SC"},
        "48": {"estado": "SC", "regiao": "Florianópolis/SC"},
        "49": {"estado": "SC", "regiao": "Chapecó/SC"},
        "51": {"estado": "RS", "regiao": "Porto Alegre/RS"},
        "53": {"estado": "RS", "regiao": "Pelotas/RS"},
        "54": {"estado": "RS", "regiao": "Caxias do Sul/RS"},
        "55": {"estado": "RS", "regiao": "Santa Maria/RS"},
        "61": {"estado": "DF", "regiao": "Brasília/DF"},
        "62": {"estado": "GO", "regiao": "Goiânia/GO"},
        "63": {"estado": "TO", "regiao": "Palmas/TO"},
        "64": {"estado": "GO", "regiao": "Rio Verde/GO"},
        "65": {"estado": "MT", "regiao": "Cuiabá/MT"},
        "66": {"estado": "MT", "regiao": "Rondonópolis/MT"},
        "67": {"estado": "MS", "regiao": "Campo Grande/MS"},
        "68": {"estado": "AC", "regiao": "Rio Branco/AC"},
        "69": {"estado": "RO", "regiao": "Porto Velho/RO"},
        "71": {"estado": "BA", "regiao": "Salvador/BA"},
        "73": {"estado": "BA", "regiao": "Ilhéus/BA"},
        "74": {"estado": "BA", "regiao": "Juazeiro/BA"},
        "75": {"estado": "BA", "regiao": "Feira de Santana/BA"},
        "77": {"estado": "BA", "regiao": "Barreiras/BA"},
        "79": {"estado": "SE", "regiao": "Aracaju/SE"},
        "81": {"estado": "PE", "regiao": "Recife/PE"},
        "82": {"estado": "AL", "regiao": "Maceió/AL"},
        "83": {"estado": "PB", "regiao": "João Pessoa/PB"},
        "84": {"estado": "RN", "regiao": "Natal/RN"},
        "85": {"estado": "CE", "regiao": "Fortaleza/CE"},
        "86": {"estado": "PI", "regiao": "Teresina/PI"},
        "87": {"estado": "PE", "regiao": "Petrolina/PE"},
        "88": {"estado": "CE", "regiao": "Juazeiro do Norte/CE"},
        "89": {"estado": "PI", "regiao": "Picos/PI"},
        "91": {"estado": "PA", "regiao": "Belém/PA"},
        "92": {"estado": "AM", "regiao": "Manaus/AM"},
        "93": {"estado": "PA", "regiao": "Santarém/PA"},
        "94": {"estado": "PA", "regiao": "Marabá/PA"},
        "95": {"estado": "RR", "regiao": "Boa Vista/RR"},
        "96": {"estado": "AP", "regiao": "Macapá/AP"},
        "97": {"estado": "AM", "regiao": "Coari/AM"},
        "98": {"estado": "MA", "regiao": "São Luís/MA"},
        "99": {"estado": "MA", "regiao": "Imperatriz/MA"},
    }
    
    
    OPERATOR_PREFIXES = {
        "11": {  
            "9": {"VIVO": ["96", "97", "98", "99"], "TIM": ["94", "95"], "CLARO": ["92", "93"], "OI": ["91"]},
            "3": {"VIVO": ["30-39"], "TIM": ["20-29"], "CLARO": ["10-19"]},
        },
        "83": {  
            "9": {"VIVO": ["96", "97"], "TIM": ["94", "95"], "CLARO": ["92", "93"], "OI": ["91"]},
            "3": {"VIVO": ["32-35"], "TIM": ["21-25"], "CLARO": ["11-15"]},
        },
    
    }
    
    @staticmethod
    def consulta_api_portabilidade(phone: str) -> Optional[Dict]:
        """Consulta API de portabilidade"""
        try:
            response = requests.get(
                f"https://api.portabilidade.com.br/v1/consulta/{phone}",
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'operadora': data.get('operadora', 'Desconhecida'),
                    'cidade': data.get('cidade', 'Desconhecida'),
                    'uf': data.get('uf', '??'),
                    'portabilidade': data.get('portabilidade', False)
                }
        except Exception as e:
            logger.debug(f"API portabilidade falhou: {e}")
        
        return None
    
    @staticmethod
    def get_operator_by_prefix(ddd: str, prefixo: str, tipo: str) -> str:
        """Determina operadora pelo prefixo"""
        if ddd not in PhoneLookup.OPERATOR_PREFIXES:
            return "Desconhecida"
        
        ddd_data = PhoneLookup.OPERATOR_PREFIXES[ddd]
        
        if tipo == "MÓVEL":
        
            primeira_part = prefixo[0] if len(prefixo) > 0 else ""
            
            if primeira_part in ddd_data:
                operadores = ddd_data[primeira_part]
                for operadora, prefixos in operadores.items():
                    for pref in prefixos:
                        if '-' in pref:  
                            inicio, fim = map(int, pref.split('-'))
                            if inicio <= int(prefixo[:2]) <= fim:
                                return operadora
                        elif prefixo.startswith(pref):
                            return operadora
        
        return "Desconhecida"
    
    @staticmethod
    def lookup(phone: str) -> PhoneInfo:
        """Consulta principal do telefone"""
        
        cached = CacheManager.load(phone)
        if cached:
            logger.info(f"Dados do cache para {phone}")
            return PhoneInfo(**cached)
        
        
        valido, tipo, partes = PhoneValidator.validate(phone)
        
        if not valido:
            return PhoneInfo(
                numero=phone,
                ddd="",
                prefixo="",
                sufixo="",
                valido=False,
                tipo="INVÁLIDO"
            )
        
        
        api_data = PhoneLookup.consulta_api_portabilidade(phone)
        
        
        ddd = partes['ddd']
        ddd_info = PhoneLookup.DDD_DATABASE.get(ddd, {"estado": "??", "regiao": "Desconhecida"})
        
    
        if api_data:
            operadora = api_data['operadora']
            cidade = api_data['cidade']
            uf = api_data['uf']
            portabilidade = api_data['portabilidade']
        else:
            operadora = PhoneLookup.get_operator_by_prefix(ddd, partes.get('raw_prefixo', partes['prefixo']), tipo)
            cidade = ddd_info['regiao'].split('/')[0]
            uf = ddd_info['estado']
            portabilidade = False
        
    
        info = PhoneInfo(
            numero=phone,
            ddd=ddd,
            prefixo=partes['prefixo'],
            sufixo=partes['sufixo'],
            operadora=operadora,
            cidade=cidade,
            uf=uf,
            tipo=tipo,
            valido=True,
            portabilidade=portabilidade,
            consulta_ts=int(time.time())
        )
        
        
        CacheManager.save(phone, asdict(info))
        
        return info

class GeolocationService:
    """Serviço de geolocalização"""
    
    @staticmethod
    def get_cell_location() -> Optional[Dict[str, float]]:
        """Obtém localização aproximada por torre celular"""
        try:
            response = requests.get(
                "https://opencellid.org/cell/getInArea",
                params={
                    "key": OCEL_KEY,
                    "mcc": MCC,
                    "format": "json",
                    "limit": 1
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("cells"):
                    cell = data["cells"][0]
                    return {
                        "latitude": float(cell["lat"]),
                        "longitude": float(cell["lon"]),
                        "accuracy": cell.get("range", 0)
                    }
        except Exception as e:
            logger.debug(f"Geolocalização falhou: {e}")
        
        return None
    
    @staticmethod
    def create_ascii_map(lat: float, lon: float, size: int = 7) -> str:
        """Cria mapa ASCII simples"""
        lines = []
        center_row = size // 2
        center_col = size // 2
        
        for row in range(size):
            line_chars = []
            for col in range(size):
                if row == center_row and col == center_col:
                    line_chars.append("[X]")
                elif abs(row - center_row) <= 1 and abs(col - center_col) <= 1:
                    line_chars.append(" * ")
                else:
                    line_chars.append(" · ")
            lines.append("".join(line_chars))
        
        map_str = "\n".join(lines)
        info_str = f"\n{'═' * 40}"
        info_str += f"\n Coordenadas: {lat:.6f}, {lon:.6f}"
        info_str += f"\n  Mapa: https://maps.google.com/?q={lat},{lon}"
        info_str += f"\n{'═' * 40}"
        
        return map_str + info_str

class Exporter:
    """Classe para exportação de dados"""
    
    @staticmethod
    def export(data: PhoneInfo, format: str, filename: Optional[str] = None):
        """Exporta dados no formato especificado"""
        if not filename:
            filename = f"telefone_{data.numero}"
        
        output_file = Path(f"{filename}.{format}")
        
        try:
            if format == "json":
                output_file.write_text(
                    json.dumps(asdict(data), ensure_ascii=False, indent=2, default=str)
                )
            elif format == "csv":
                with output_file.open('w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Campo", "Valor"])
                    for field, value in asdict(data).items():
                        writer.writerow([field, str(value)])
            elif format == "txt":
                output_file.write_text(str(asdict(data)))
            
            logger.info(f"Dados exportados para: {output_file}")
        except Exception as e:
            logger.error(f"Erro ao exportar: {e}")

class ConsoleDisplay:
    """Classe para exibição no console"""
    
    @staticmethod
    def show_phone_info(info: PhoneInfo, show_map: bool = True):
        """Exibe informações do telefone formatadas"""
        if not info.valido:
            print(f"\n Número inválido: {info.numero}")
            return
        
        
        print(f"\n{'═' * 50}")
        print(f" TELEFONE: {info.formatado()}")
        print(f"{'═' * 50}")
        
        
        table_data = [
            ["Número", info.numero],
            ["DDD", info.ddd],
            ["Tipo", info.tipo],
            ["Operadora", info.operadora],
            ["Localização", f"{info.cidade}/{info.uf}"],
            ["Portabilidade", "Sim" if info.portabilidade else "Não"],
            ["Válido", "Sim" if info.valido else "Não"],
            ["Consulta", datetime.fromtimestamp(info.consulta_ts).strftime("%d/%m/%Y %H:%M:%S")]
        ]
        
        if info.latitude and info.longitude:
            table_data.append([" Latitude", f"{info.latitude:.6f}"])
            table_data.append([" Longitude", f"{info.longitude:.6f}"])
        
        print(tabulate(table_data, headers=["Campo", "Valor"], tablefmt="rounded_grid"))
        
        
        if show_map and info.latitude and info.longitude:
            print(f"\n{'═' * 50}")
            print("  MAPA DE LOCALIZAÇÃO APROXIMADA")
            print(f"{'═' * 50}")
            print(GeolocationService.create_ascii_map(info.latitude, info.longitude))
    
    @staticmethod
    def show_batch_summary(results: List[PhoneInfo]):
        """Exibe resumo de consultas em lote"""
        if not results:
            return
        
        valid_count = sum(1 for r in results if r.valido)
        mobile_count = sum(1 for r in results if r.tipo == "MÓVEL")
        fixed_count = sum(1 for r in results if r.tipo == "FIXO")
        
        print(f"\n{'═' * 60}")
        print(" RESUMO DA CONSULTA EM LOTE")
        print(f"{'═' * 60}")
        print(f"• Total de números processados: {len(results)}")
        print(f"• Números válidos: {valid_count}")
        print(f"• Celulares (MÓVEL): {mobile_count}")
        print(f"• Fixos: {fixed_count}")
        print(f"• Inválidos: {len(results) - valid_count}")
        print(f"{'═' * 60}")
        
        
        operadoras = {}
        for r in results:
            if r.valido:
                operadoras[r.operadora] = operadoras.get(r.operadora, 0) + 1
        
        if operadoras:
            print("\n DISTRIBUIÇÃO POR OPERADORA:")
            for operadora, count in sorted(operadoras.items(), key=lambda x: x[1], reverse=True):
                print(f"  {operadora}: {count}")

def main():
    """Função principal"""
    parser = argparse.ArgumentParser(
        description=" Rastreador de Telefones Brasileiros - Versão Melhorada",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
%(prog)s 83993437321                    # Consulta único número
%(prog)s 11 987654321 21 912345678      # Consulta múltiplos números
%(prog)s @numeros.txt                   # Consulta a partir de arquivo
%(prog)s -q 83993437321                 # Saída JSON (quiet mode)
%(prog)s 83993437321 -o json            # Exporta para JSON
%(prog)s -h                             # Ajuda completa
        """
    )
    
    parser.add_argument(
        "numeros",
        nargs="*",
        help="Números de telefone ou arquivo com @ prefixo (ex: @lista.txt)"
    )
    
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Saída em JSON (uma linha por número)"
    )
    
    parser.add_argument(
        "-o", "--output",
        choices=["json", "csv", "txt"],
        help="Exporta cada número para arquivo"
    )
    
    parser.add_argument(
        "-m", "--no-map",
        action="store_true",
        help="Não mostrar mapa ASCII"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Modo verboso (mais detalhes)"
    )
    
    parser.add_argument(
        "-c", "--clear-cache",
        action="store_true",
        help="Limpa cache antes da consulta"
    )
    
    args = parser.parse_args()
    
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    
    if args.clear_cache:
        try:
            for cache_file in CACHE_DIR.glob("*.json"):
                cache_file.unlink()
            logger.info("Cache limpo com sucesso!")
        except Exception as e:
            logger.error(f"Erro ao limpar cache: {e}")
    
    
    phone_numbers = []
    
    if not args.numeros:
        
        try:
            while True:
                entrada = input("\n Digite um número (ou Enter para sair): ").strip()
                if not entrada:
                    break
                phone_numbers.append(entrada)
        except (EOFError, KeyboardInterrupt):
            print("\n Operação cancelada pelo usuário.")
            sys.exit(0)
    else:
        
        for item in args.numeros:
            if item.startswith('@'):
                
                file_path = Path(item[1:])
                if file_path.exists():
                    try:
                        numbers_from_file = file_path.read_text().split()
                        phone_numbers.extend(numbers_from_file)
                        logger.info(f"Carregados {len(numbers_from_file)} números de {file_path}")
                    except Exception as e:
                        logger.error(f"Erro ao ler arquivo {file_path}: {e}")
                else:
                    logger.error(f"Arquivo não encontrado: {file_path}")
            else:
                
                phone_numbers.append(item)
    
    if not phone_numbers:
        logger.warning("Nenhum número para consultar.")
        return
    
    
    results = []
    
    for raw_number in phone_numbers:
        
        normalized = PhoneValidator.normalize(raw_number)
        if not normalized:
            logger.warning(f"Número inválido: {raw_number}")
            continue
        
        logger.info(f"Consultando: {normalized}")
        
        
        info = PhoneLookup.lookup(normalized)
        
        
        if not info.latitude or not info.longitude:
            geo = GeolocationService.get_cell_location()
            if geo:
                info.latitude = geo["latitude"]
                info.longitude = geo["longitude"]
        
        
        if args.quiet:
            print(json.dumps(asdict(info), ensure_ascii=False))
        else:
            ConsoleDisplay.show_phone_info(info, not args.no_map)
        
        
        if args.output:
            Exporter.export(info, args.output)
        
        results.append(info)
    
    
    if len(results) > 1 and not args.quiet:
        ConsoleDisplay.show_batch_summary(results)

if __name__ == "__main__":
    import sys
    numero = sys.argv[1]
    info = PhoneLookup.lookup(numero)
    print(info)