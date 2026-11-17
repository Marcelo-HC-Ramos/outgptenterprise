# Colocar o OutGPT no seu domínio (Cloudflare)

Resultado: o sistema completo (login, banco de dados, cursos e IA) acessível em **https://outgpt.ramosys.com.br**, com HTTPS e a
proteção do Cloudflare, sem abrir portas no roteador.

## Como funciona (e o que o Cloudflare não faz)
O Cloudflare Pages e o Workers não executam um servidor Python com banco SQLite e busca vetorial, então o sistema continua rodando
**num computador seu** (ou num servidor), e o **Cloudflare Tunnel** liga esse servidor ao seu domínio:
```
visitante --HTTPS--> Cloudflare (ramosys.com.br) --túnel--> cloudflared --> servidor OutGPT (porta 8000)
```
- Seu domínio **já está no Cloudflare** (servidores de nome `nina` e `nikon.ns.cloudflare.com`), então não precisa mudar nada no Registro.br.
- Enquanto o computador estiver ligado e o `PUBLICAR.bat` aberto, o site está no ar. Para ficar **24 horas**, use um servidor
  (veja "Servidor sempre ligado", abaixo).

## Passo a passo (uns 10 minutos)
**A. No painel do Cloudflare (você faz uma vez)**
1. Entre em **one.dash.cloudflare.com** (Zero Trust). Se for o primeiro acesso, escolha um nome para a equipe e o plano **Free**
   (o Cloudflare pode pedir um cartão para ativar, sem cobrança no plano gratuito).
2. Vá em **Networks > Tunnels > Create a tunnel** > tipo **Cloudflared** > nome `outgpt` > *Save tunnel*.
3. Na tela seguinte, **copie o comando de instalação inteiro** (ele contém o token). Você vai colar no passo B.
4. Em **Public Hostname** (ou "Published application routes") adicione: *Subdomain* `outgpt`, *Domain* `ramosys.com.br`,
   *Service* tipo **HTTP**, URL `localhost:8000` > Save. O Cloudflare cria o registro DNS sozinho.
   (Quer usar o endereço raiz `ramosys.com.br`? Deixe o *Subdomain* vazio e, no `PUBLICAR.bat`, informe `ramosys.com.br`.)

**B. No seu computador**
1. Dê dois cliques em **`PUBLICAR.bat`** (na pasta do projeto).
2. Na primeira vez ele faz as perguntas de sempre (seu login, chave da IA, empresa) e depois pede o **token do túnel**:
   cole o comando que você copiou (ele extrai o token). O token fica só em `backend/.env`.
3. Se o `cloudflared` não estiver instalado, ele oferece instalar pelo `winget` (pacote oficial do Cloudflare); responda `S`.
4. Aguarde a mensagem **">>> NO AR: https://outgpt.ramosys.com.br"** e abra o endereço. Entre com o login que você criou.

Nas próximas vezes, `PUBLICAR.bat` não pergunta nada: liga o servidor e o túnel. Para encerrar, feche as duas janelas.

## Recomendações de segurança no Cloudflare (painel do domínio)
- **SSL/TLS > Edge Certificates:** ative *Always Use HTTPS*.
- **Security > Bots:** ligue *Bot Fight Mode*. **Security > WAF > Rate limiting rules:** regra para `outgpt.ramosys.com.br/api/login`
  (por exemplo, no máximo 10 requisições por minuto por IP). O sistema já bloqueia a conta após 5 senhas erradas, e isso reforça.
- Senhas fortes (mínimo de 10 caracteres, imposto pelo sistema) e **nunca compartilhe** o token do túnel nem a chave da IA.
- Opcional: **Cloudflare Access** (Zero Trust > Access > Applications) para exigir um código por e-mail antes mesmo da tela de login,
  se o sistema for só para um grupo conhecido. Não use para a página de pesquisa pública (`/pesquisa.html`), que deve ficar aberta.

## Limites que você precisa saber
- **Computador desligado ou em suspensão = site fora do ar.** Em Windows, desative a suspensão enquanto o sistema precisa estar no ar.
- Requisições que passam de ~100 segundos sem resposta recebem erro 524 do Cloudflare (por exemplo, indexar um PDF gigante). Arquivos
  normais (até alguns MB) ficam bem abaixo disso. O limite de envio do sistema é 8 MB por arquivo.
- O endereço de teste de um túnel rápido (`trycloudflare.com`) muda toda vez; use o túnel nomeado deste guia para um endereço fixo.
- Faça backups (`python backup.py`) e guarde-os fora do computador.

## Servidor sempre ligado (24h)
Num servidor com Docker (VPS ou um computador dedicado), use o `docker-compose.yml`, que sobe o sistema e o `cloudflared` juntos:
1. Copie `docker-compose.exemplo.env` para `.env` e preencha `CLOUDFLARE_TUNNEL_TOKEN` e `OUTGPT_SETUP_TOKEN` (valor longo e aleatório).
2. No Public Hostname do túnel, aponte o *Service* para **`http://outgpt:8000`** (o nome do contêiner do sistema).
3. `docker compose up -d --build`. Abra o endereço: na primeira vez aparece **Primeiro acesso**; use o `OUTGPT_SETUP_TOKEN` para criar o master.
4. Backup: `docker compose exec outgpt python backup.py /data/backups` e copie a pasta para fora do servidor.

## Solução de problemas
| Sintoma | O que fazer |
|---|---|
| Erro 1033 / "Cloudflare Tunnel error" | O `cloudflared` não está conectado: confira se a janela do `PUBLICAR.bat` está aberta e o túnel "Healthy" no painel. |
| Erro 502 | O túnel está ligado, mas o servidor não: confira a janela `server.py` e se o *Service* é `http://localhost:8000`. |
| Erro 403 ao entrar ("Origem não permitida") | O endereço acessado é diferente do informado no `PUBLICAR.bat` (`OUTGPT_DOMINIO`). Use o mesmo endereço. |
| O domínio não abre | No painel do domínio (DNS), deve existir um CNAME `outgpt` para `...cfargotunnel.com` (criado pelo Public Hostname). |
| Token recusado no `PUBLICAR.bat` | Copie de novo o comando inteiro do passo A.3 (o token é longo e começa com `eyJ`). |

## O que foi testado
O servidor atrás de proxy/Cloudflare (IP real, domínio aceito, cookies seguros), a leitura do token e o `docker-compose.yml` têm testes
automáticos, e o GitHub Actions executa um teste ponta a ponta por um túnel temporário do Cloudflare (sem conta). O passo a passo no
painel do **seu** Cloudflare e o `winget` dependem da sua conta e do seu computador e não puderam ser executados por quem escreveu estes arquivos.