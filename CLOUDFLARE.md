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

## Passo a passo (sem cartão)
Este é o caminho testado: **não ativa o Zero Trust e não pede cartão ou PayPal**. O programa `cloudflared` cria o túnel e o registro DNS
depois que você autoriza o domínio no navegador.
1. Dê dois cliques em **`PUBLICAR.bat`** (na pasta do projeto).
2. Na **primeira vez** ele faz, em ordem:
   - as perguntas de sempre (seu login de dono, chave da IA opcional, empresa);
   - instala o `cloudflared` pelo `winget` (pacote oficial `Cloudflare.cloudflared`; responda `S`; não precisa de administrador);
   - abre o login do Cloudflare no navegador: entre na sua conta, escolha **ramosys.com.br** e clique em **Autorizar**;
   - cria o túnel `outgpt` e o registro DNS `outgpt.ramosys.com.br` sozinho, liga o servidor e o túnel.
3. Aguarde **">>> NO AR: https://outgpt.ramosys.com.br"** e abra o endereço. Entre com o login que você criou.

Nas próximas vezes `PUBLICAR.bat` não pergunta nada: liga o servidor e o túnel. Para encerrar, feche as duas janelas.
Quer outro endereço (por exemplo o raiz `ramosys.com.br`)? Informe-o quando o `PUBLICAR.bat` perguntar, na primeira vez.

### Alternativa com token (painel Zero Trust)
Também funciona, mas o Cloudflare **exige cartão ou PayPal** para ativar o Zero Trust, mesmo no plano gratuito (US$ 0). No painel:
*Zero Trust > Networks > Tunnels > Create a tunnel* (Cloudflared), copie o comando de instalação, adicione o *Public Hostname*
(`outgpt` + `ramosys.com.br` > HTTP `localhost:8000`) e cole o comando quando o `PUBLICAR.bat` pedir o token.
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
Para o site não depender do seu computador, rode-o em um VPS: o guia **[SERVIDOR.md](SERVIDOR.md)** traz o passo a passo com um instalador
(`servidor/instalar.sh`) que reaproveita o **mesmo túnel sem cartão** deste guia (você só copia o arquivo de credenciais do túnel) e usa o
`docker-compose.servidor.yml`.

Se você criou o túnel no painel Zero Trust (com token), use o `docker-compose.yml`:
1. Copie `docker-compose.exemplo.env` para `.env` e preencha `CLOUDFLARE_TUNNEL_TOKEN` e `OUTGPT_SETUP_TOKEN` (valor longo e aleatório).
2. No Public Hostname do túnel, aponte o *Service* para **`http://outgpt:8000`** (o nome do contêiner do sistema).
3. `docker compose up -d --build`. Na primeira vez aparece **Primeiro acesso**; use o `OUTGPT_SETUP_TOKEN` para criar o master.
4. Backup: `docker compose exec outgpt python backup.py /data/backups` e copie a pasta para fora do servidor.
(O instalador também aceita o token: cole-o quando ele pedir as credenciais do túnel.)

## Solução de problemas
| Sintoma | O que fazer |
|---|---|
| Erro 1033 / "Cloudflare Tunnel error" | O `cloudflared` não está conectado: confira se a janela do `PUBLICAR.bat` está aberta e o túnel "Healthy" no painel. |
| Erro 502 | O túnel está ligado, mas o servidor não: confira a janela `server.py` e se o *Service* é `http://localhost:8000`. |
| Erro 403 ao entrar ("Origem não permitida") | O endereço acessado é diferente do informado no `PUBLICAR.bat` (`OUTGPT_DOMINIO`). Use o mesmo endereço. |
| O domínio não abre | No painel do domínio (DNS), deve existir um CNAME `outgpt` para `...cfargotunnel.com` (criado pelo Public Hostname). |
| Token recusado no `PUBLICAR.bat` | Copie de novo o comando inteiro do passo A.3 (o token é longo e começa com `eyJ`). |

## O que foi testado
- **No seu computador, em 17/11/2026:** instalação do `cloudflared`, autorização do domínio, criação do túnel `outgpt` e do DNS `outgpt.ramosys.com.br`,
  segunda execução reaproveitando tudo, e o endereço público respondendo (`/saude`, página inicial, cabeçalhos de segurança, rotas protegidas):
  7 de 7 verificações em `https://outgpt.ramosys.com.br`.
- **No GitHub Actions, a cada envio:** o servidor atrás de proxy/Cloudflare (IP real, domínio aceito, cookies seguros), a leitura do túnel e o
  `docker-compose.yml`, mais um teste ponta a ponta por um túnel temporário.
- **No GitHub Actions e aqui:** o instalador do servidor (49 verificações: credenciais, `.env`, configuração do túnel, memória de troca) e a validação do `docker-compose.servidor.yml`.
- **Ainda não testado:** o login pelo endereço público (depende de você criar o seu login de dono) e o instalador/`docker-compose` em um VPS real.