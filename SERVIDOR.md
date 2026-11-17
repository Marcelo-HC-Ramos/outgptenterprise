# Deixar o OutGPT no ar 24 horas (servidor VPS)

Com isto o site **não depende mais do seu computador**: ele passa a rodar em um servidor pequeno alugado (VPS), ligado o tempo todo,
no mesmo endereço (`https://outgpt.ramosys.com.br`), com o mesmo túnel do Cloudflare (sem cartão no Cloudflare e sem abrir portas).

## Custo e o que escolher
Não existe hospedagem **gratuita** que guarde o banco de dados: os planos grátis sem cartão apagam o disco ao reiniciar ou "dormem",
e o OutGPT precisa de disco (logins, conteúdos e busca). O caminho é um VPS pequeno:

| Item | O que precisa |
|---|---|
| Sistema | **Ubuntu 22.04 ou 24.04** (ou Debian) |
| Memória | **2 GB de RAM** (com 1 GB funciona; o instalador cria memória de troca) |
| Disco / CPU | 20 GB e 1 vCPU bastam para equipes pequenas |
| Pagamento | Provedores brasileiros costumam aceitar **Pix e boleto**; os internacionais, cartão ou PayPal |
| Preço (referência) | Planos de 2 GB aparecem a partir de ~R$ 30/mês no Brasil e ~€ 4 a 6/mês fora (valores variam e mudam: confira na página do provedor) |
| IA (separado) | Cada pergunta usa a API da Anthropic (veja "Custos da IA", abaixo) |

> O instalador foi testado automaticamente (geração dos arquivos, credenciais, `.env`) e o `docker-compose.servidor.yml` é validado pelo GitHub Actions
> a cada envio, mas **ainda não foi executado em um VPS real**. Se algo falhar, a mensagem na tela diz o passo; me envie o texto.

## Passo a passo
**1. Contrate o VPS** (Ubuntu, 2 GB) e anote o **IP** e a senha de `root` (ou cadastre sua chave SSH).

**2. Feche o túnel do seu PC.** Se o `PUBLICAR.bat` estiver aberto, feche as duas janelas. Dois computadores no mesmo túnel dividem os visitantes
e uns caem na cópia velha do seu PC.

**3. Copie as credenciais do túnel** (no seu Windows, em um PowerShell). É o arquivo que o `PUBLICAR.bat` criou; este comando copia o conteúdo para a área de transferência:
```powershell
Get-ChildItem "$env:USERPROFILE\.cloudflared\*-*-*-*-*.json" | Get-Content | Set-Clipboard
```
Esse conteúdo é **secreto** (quem o tiver controla o seu túnel): não envie para ninguém nem publique.

**4. Conecte no servidor e rode o instalador** (no PowerShell do Windows, troque `IP-DO-SERVIDOR`):
```powershell
ssh root@IP-DO-SERVIDOR
```
Já dentro do servidor:
```bash
curl -fsSLo instalar.sh https://raw.githubusercontent.com/Marcelo-HC-Ramos/outgptenterprise/main/servidor/instalar.sh
sudo sh instalar.sh
```
O instalador pergunta (tudo com padrão sensato):
- **Endereço**: Enter para `outgpt.ramosys.com.br`.
- **Credenciais do túnel**: clique com o botão direito para colar (o texto fica oculto) e tecle Enter.
- **Chave da API da Anthropic**: cole (oculta) ou Enter para colar depois pelo site.
- **Procedimentos de exemplo**: `S` carrega os 100 manuais em uma empresa "Minha Empresa" (dá para apagar depois).

Ele instala o Docker, sobe o sistema e o túnel, espera responder e mostra **"NO AR"** com a **senha do primeiro acesso**. A primeira vez leva alguns minutos (baixa o modelo de busca).

**5. Primeiro acesso.** Abra `https://outgpt.ramosys.com.br`, informe a senha mostrada pelo instalador na tela **Primeiro acesso** e crie o seu login de dono (master).
Em **Administração > Inteligência artificial**, confirme "Conexão ok".

## Usar com outras pessoas
- Não existe cadastro aberto: você cria os acessos em **Usuários** e passa o e-mail e uma senha provisória (a pessoa troca em **Minha senha**).
- Crie uma empresa em **Empresas** e carregue os conteúdos em **Biblioteca** (arquivos TXT, MD, PDF, DOCX ou CSV).
- A página pública de pesquisa (`/pesquisa.html`) continua aberta para qualquer pessoa; os resultados são só do master.

## Custos da IA (importante)
Cada pergunta respondida é uma chamada paga na **sua** chave, feita por qualquer usuário. Antes de divulgar:
1. No console da Anthropic (console.anthropic.com), defina um **limite mensal de gasto** para a chave.
2. Para gastar bem menos, use o modelo menor: `nano /opt/outgpt/.env`, troque para `OUTGPT_MODELO=claude-haiku-5-5` e rode `cd /opt/outgpt && docker compose up -d`.
3. O sistema já limita **20 perguntas por minuto por usuário**.

## Manutenção
| Tarefa | Comando (no servidor) |
|---|---|
| Atualizar para a versão nova do GitHub | `sudo sh /opt/outgpt/servidor/instalar.sh` (mantém banco, logins e configurações) |
| Ver o que está acontecendo | `cd /opt/outgpt && docker compose logs --tail 50 outgpt` (ou `cloudflared`) |
| Reiniciar | `cd /opt/outgpt && docker compose restart` |
| Backup | Automático todo dia às 03:17 (14 cópias, dentro do volume). **Copie para fora do servidor** de vez em quando: `cd /opt/outgpt && docker compose cp outgpt:/data/backups ./copia-backups` e baixe a pasta com `scp` |
| Trocar o túnel | `sudo python3 /opt/outgpt/servidor/instalar.py --trocar-tunel` |

Segurança do servidor: nenhuma porta do sistema fica aberta na internet (só o túnel conversa com ele). A única porta exposta é a do SSH:
use uma **chave SSH** em vez de senha quando puder e mantenha o Ubuntu atualizado (`sudo apt update && sudo apt upgrade`).
Sobre LGPD e privacidade dos dados enviados à IA, veja "Cuidados antes de abrir para outras pessoas" no [DEPLOY.md](DEPLOY.md).

## Se algo der errado
| Sintoma | O que fazer |
|---|---|
| "Não consegui ler as credenciais do túnel" | Refaça o passo 3 e cole de novo (o texto começa com `{"AccountTag"`). |
| Instalador diz que o sistema não respondeu | Servidor com pouca memória ou disco: veja o log mostrado na tela; um VPS de 2 GB resolve. |
| Erro 1033 no site | O túnel não conectou: `docker compose logs --tail 30 cloudflared`. Confirme que o túnel do PC está fechado e que o domínio é o mesmo do túnel. |
| Erro 403 ao entrar ("Origem não permitida") | O endereço aberto é diferente do informado no instalador. Rode-o de novo com o endereço certo. |
| Erro 502 | O túnel está ligado mas o sistema não: `docker compose ps` e `docker compose logs outgpt`. |

Os dados que você criou no seu PC (empresa, conteúdos, usuários) **não são copiados**: o servidor começa vazio (com os exemplos, se aceitou). Recarregue os conteúdos pela Biblioteca.
