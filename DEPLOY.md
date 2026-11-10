# Publicar o OutGPT na internet

Este guia coloca o sistema completo (login, banco de dados, cursos e IA) no ar com HTTPS, para que outras pessoas
usem pelo navegador. O GitHub Pages **não serve** para isso: ele só hospeda a demonstração (sem Python).

> **Status:** os arquivos de publicação (`Dockerfile`, `render.yaml`, `fly.toml`) e o modo servidor foram preparados e o
> modo servidor foi testado localmente (primeiro acesso, cookie Secure, HSTS, proxy, limite por IP, `/saude`, backup).
> O **build da imagem Docker e a publicação em si ainda não foram executados**: não havia Docker nem conta de
> hospedagem no computador de desenvolvimento. Siga o passo a passo e, se algo falhar, o log da plataforma mostra o motivo.

## O que você precisa
| Item | Detalhe |
|---|---|
| Hospedagem com Docker | Render, Fly.io ou um servidor próprio (VPS). Precisa de **disco persistente** para o banco. |
| Memória | O servidor usa ~650 MB com o modelo de busca carregado (medido). Use **no mínimo 1 GB, 2 GB com folga**. |
| HTTPS | As plataformas acima já entregam HTTPS. Sem HTTPS o login por cookie seguro não funciona. |
| Chave da API (opcional) | Para a IA escrever as respostas. Pode ser colada depois, na tela de administração. |
| Custos | Hospedagem (plano pago por causa do disco e da memória) + uso da API da IA. Confira os preços atuais nos sites. |

## Variáveis de ambiente (a imagem Docker já define as marcadas com ✔)
| Variável | Função |
|---|---|
| `OUTGPT_SETUP_TOKEN` | **Você define.** Senha de uso único para criar o primeiro usuário master pela tela "Primeiro acesso". Depois do primeiro master, é ignorada. Use um valor longo e aleatório. |
| `ANTHROPIC_API_KEY` | Chave da IA (opcional: dá para configurar pela tela Administração > Inteligência artificial). |
| `OUTGPT_MODELO` | Modelo (padrão `claude-opus-5-5`; `claude-haiku-5-5` custa bem menos). |
| `OUTGPT_HOST` ✔ | `0.0.0.0` para aceitar conexões da rede da hospedagem. |
| `PORT` | Porta; a hospedagem costuma definir (o padrão é 8000). |
| `OUTGPT_DB`, `OUTGPT_CHROMA`, `OUTGPT_ENV_ARQ` ✔ | Caminhos no volume `/data` (banco, índice de busca e a chave salva pela tela). |
| `OUTGPT_COOKIE_SECURE` ✔ | `1`: cookie de sessão só por HTTPS e cabeçalho HSTS. |
| `OUTGPT_CONFIAR_PROXY` ✔ | `1`: usa o IP real do cliente (`X-Forwarded-For` do proxy) nos limites de tentativas. Só ative atrás de um proxy confiável. |

## Opção A: Render
1. Suba o projeto para o GitHub (já está) e crie uma conta em render.com.
2. **New > Blueprint** e escolha o repositório: o Render lê o `render.yaml` (serviço Docker, disco de 2 GB em `/data`,
   `OUTGPT_SETUP_TOKEN` gerado automaticamente). Confira o plano (precisa de pelo menos 1 GB de RAM).
3. Quando terminar o deploy, copie o valor de `OUTGPT_SETUP_TOKEN` em *Environment* e abra a URL do serviço.

## Opção B: Fly.io
```bash
fly launch --no-deploy --copy-config          # usa o fly.toml (troque o nome do app por um único)
fly volumes create dados --size 2 --region gru
fly secrets set OUTGPT_SETUP_TOKEN="$(openssl rand -hex 24)"
fly deploy
```
Anote o valor usado em `OUTGPT_SETUP_TOKEN`. Mantenha **uma única máquina** (o SQLite não suporta várias escrevendo ao mesmo tempo).

## Opção C: servidor próprio (VPS) com HTTPS automático
```bash
docker build -t outgpt .
docker run -d --name outgpt --restart unless-stopped -p 127.0.0.1:8000:8000 -v outgpt-dados:/data \
  -e OUTGPT_SETUP_TOKEN="troque-por-um-valor-longo" outgpt
```
Coloque um proxy com HTTPS na frente, por exemplo o Caddy (certificado automático), com este `Caddyfile`:
```
seu-dominio.com.br {
    reverse_proxy 127.0.0.1:8000
}
```
Se for acessar por HTTP puro (apenas em teste), rode o contêiner com `-e OUTGPT_COOKIE_SECURE=0`.

## Primeiro acesso
1. Abra o endereço do site: aparece **Primeiro acesso**. Informe o token (`OUTGPT_SETUP_TOKEN`), seu nome, e-mail e senha.
   Isso cria o usuário **master** (dono do sistema) e a tela deixa de existir.
2. Entre com o e-mail e a senha. Em **Administração > Inteligência artificial**, cole a chave da API (ou defina `ANTHROPIC_API_KEY`).
3. Em **Empresas**, crie a empresa; em **Biblioteca**, importe ou envie os conteúdos; em **Usuários**, cadastre os acessos.

## Backup e restauração
O que importa está em `/data/outgpt.db` (o índice de busca é refeito sozinho a partir do banco).
```bash
docker exec outgpt python backup.py /data/backups          # cópia consistente; mantém as 14 mais recentes
# copie /data/backups para fora do servidor (outro disco, armazenamento na nuvem...)
```
Na Fly.io: `fly ssh console -C "python backup.py /data/backups"`. Para restaurar: pare o serviço, substitua `/data/outgpt.db`
pelo arquivo de backup e inicie de novo. Faça backups com frequência: um disco perdido sem backup perde tudo.

## Cuidados antes de abrir para outras pessoas
- **Privacidade (LGPD):** os trechos dos manuais e as perguntas (já anonimizadas) são enviados à API da IA para gerar a resposta.
  Informe isso aos usuários, evite cadastrar dados pessoais nos conteúdos e verifique os termos do provedor de IA e da hospedagem.
- **Senhas:** não há recuperação por e-mail. O master pode redefinir a senha de qualquer usuário na tela Usuários; guarde bem a do master.
- **Instância única:** o SQLite atende bem equipes pequenas e médias; não rode várias cópias do serviço no mesmo banco.
- **Custos da IA:** cada pergunta é uma chamada paga. Há limite de 20 perguntas por minuto por usuário; para economizar,
  use `OUTGPT_MODELO=claude-haiku-5-5`.
- **Atualizações:** `git pull` + novo deploy; o banco é atualizado sozinho na inicialização (`init_db.py`).
- **Monitoramento:** o endereço `/saude` responde `ok` e serve para o monitor/balanceador.

## Demonstração gratuita (GitHub Pages)
A pasta `docs/` continua publicável no GitHub Pages como **demonstração**: sem login, sem IA e sem banco, com conteúdo de exemplo.
Para o sistema completo use uma das opções acima.
