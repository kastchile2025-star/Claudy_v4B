# Skills de Claudy

Claudy usa skills como instrucciones Markdown guardadas en archivos `SKILL.md`.

## Ubicaciones

| Tipo | Ruta | Uso |
| --- | --- | --- |
| Proyecto | `skills/<nombre>/SKILL.md` | Skills versionados con el repo. |
| Usuario | `~/.claudy/skills/<nombre>/SKILL.md` | Skills instalados desde internet o desde una URL. |
| Indice local | `~/.claudy/skills/README.md` | README generado automaticamente con los skills instalados por el usuario. |

## Instalacion desde el chat web

Puedes pedirlo en lenguaje natural:

```text
instala una skill para leer pdf
```

O usar comandos slash:

```text
/skill_find pdf
/skill_install_best pdf
/skill_install https://github.com/vercel-labs/skills/blob/main/skills/find-skills/SKILL.md
```

## Instalacion desde el CLI

```text
/find-skill pdf
/install-skill pdf
```

## Como decide Claudy

1. Detecta frases que mencionan `skill`, `skills`, `habilidad` o `habilidades`.
2. Limpia la consulta para dejar el tema principal. Por ejemplo, `instala una skill para leer pdf` se transforma en `pdf`.
3. Busca candidatos en `skills.sh`.
4. Intenta descargar el `SKILL.md` desde el repositorio GitHub del candidato.
5. Si la fuente es GitHub, copia tambien archivos auxiliares del mismo directorio del skill.
6. Guarda el skill en `~/.claudy/skills/<nombre>/SKILL.md`.
7. Actualiza `~/.claudy/skills/README.md`.

## Seguridad

Los skills son texto de instrucciones que Claudy puede usar como contexto. Instala solo fuentes confiables y revisa el contenido si el skill pide secretos, credenciales o acciones riesgosas.
