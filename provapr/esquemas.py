"""Os 2 esquemas da arquitetura (seção 4) e um validador mínimo de JSON Schema."""
import re


class ErroEsquema(ValueError):
    pass


def esquema_criterios(metodos):
    """Esquema da chamada 1; o enum recebe os ids achados pela regex."""
    if metodos:
        funcoes = {"type": "array", "items": {"type": "string", "enum": sorted(metodos)}}
    else:
        funcoes = {"type": "array", "maxItems": 0}
    return {
        "type": "object", "additionalProperties": False, "required": ["criterios"],
        "properties": {"criterios": {
            "type": "array", "minItems": 1, "maxItems": 12,
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["id", "descricao", "funcoes", "exemplos"],
                "properties": {
                    "id": {"type": "string", "pattern": "^CA[0-9]{1,2}$"},
                    "descricao": {"type": "string", "maxLength": 300},
                    "funcoes": funcoes,
                    "exemplos": {"type": "array", "items": {"type": "string"}},
                },
            },
        }},
    }


ESQUEMA_TESTE = {
    "type": "object", "additionalProperties": False,
    "required": ["nome_teste", "corpo_metodo", "entrada", "saida_esperada", "justificativa"],
    "properties": {
        "nome_teste": {"type": "string", "pattern": "^[a-z][A-Za-z0-9_]{2,60}$"},
        "corpo_metodo": {"type": "string", "maxLength": 2000},
        "entrada": {"type": "string"},
        "saida_esperada": {"type": "string"},
        "justificativa": {"type": "string", "maxLength": 400},
    },
}

_TIPOS = {"object": dict, "array": list, "string": str}


def validar(valor, esquema, caminho="$"):
    """Levanta ErroEsquema na primeira violação. Cobre só o que os 2 esquemas usam."""
    tipo = esquema.get("type")
    if tipo and not isinstance(valor, _TIPOS[tipo]):
        raise ErroEsquema(f"{caminho}: esperado {tipo}")
    if "enum" in esquema and valor not in esquema["enum"]:
        raise ErroEsquema(f"{caminho}: {valor!r} fora do enum")
    if tipo == "string":
        if "maxLength" in esquema and len(valor) > esquema["maxLength"]:
            raise ErroEsquema(f"{caminho}: maior que {esquema['maxLength']}")
        if "pattern" in esquema and not re.search(esquema["pattern"], valor):
            raise ErroEsquema(f"{caminho}: não casa {esquema['pattern']}")
    elif tipo == "array":
        if len(valor) < esquema.get("minItems", 0):
            raise ErroEsquema(f"{caminho}: menos de {esquema['minItems']} itens")
        if "maxItems" in esquema and len(valor) > esquema["maxItems"]:
            raise ErroEsquema(f"{caminho}: mais de {esquema['maxItems']} itens")
        for i, item in enumerate(valor):
            validar(item, esquema.get("items", {}), f"{caminho}[{i}]")
    elif tipo == "object":
        props = esquema.get("properties", {})
        for campo in esquema.get("required", []):
            if campo not in valor:
                raise ErroEsquema(f"{caminho}: falta {campo}")
        if esquema.get("additionalProperties") is False:
            extras = set(valor) - set(props)
            if extras:
                raise ErroEsquema(f"{caminho}: campo extra {sorted(extras)}")
        for campo, sub in props.items():
            if campo in valor:
                validar(valor[campo], sub, f"{caminho}.{campo}")
    return valor
