# Deixar o OutGPT no ar 24 horas (servidor)

Com isto o site **não depende mais do seu computador**: ele roda em um servidor ligado o tempo todo, no mesmo endereço
(`https://outgpt.ramosys.com.br`), pelo mesmo túnel do Cloudflare (sem cartão no Cloudflare e sem abrir portas).
Um instalador (`servidor/instalar.sh`) faz o trabalho pesado; você só cria o servidor e roda dois comandos.

## Qual servidor
| | **A) Oracle Cloud "Always Free"** (grátis, pede cartão) | **B) VPS pago** |
|---|---|---|
| Custo | R$ 0 enquanto usar só recursos "Always Free" | ~R$ 30/mês no Brasil ou ~€ 4 a 6/mês fora (varia: confira no site do provedor) |
| Máquina | Ampere A1 (ARM): até 2 vCPU e 12 GB de RAM, 200 GB de disco, 10 TB/mês de saída (limites da [página oficial](https://docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm); já mudaram em 2026, confira no console) | Ubuntu 22.04/24.04 com 2 GB de RAM |
| Cartão | Exigido para verificar a identidade; não é cobrado dentro do limite gratuito | Pix/boleto em muitos provedores brasileiros |
| Riscos | Veja abaixo | Só o custo mensal |

**Riscos do Oracle grátis (leia antes):**
1. **Cadastro recusado:** cartões pré-pagos e virtuais costumam ser recusados. Use um cartão **físico, no seu nome**, com o endereço de cobrança correto.
2. **"Out of host capacity"** ao criar a máquina: é falta temporária de capacidade. Tente de novo mais tarde, escolha outro *Availability Domain* ou um tamanho menor (1 vCPU / 6 GB).
3. **Máquina ociosa pode ser recuperada:** a Oracle pode recolher máquinas gratuitas cujo uso de CPU, rede e memória fique abaixo de 20% por 7 dias. O OutGPT é leve, então isso pode acontecer. Por isso: faça **backup fora do servidor** (veja "Manutenção") e use um **monitor gratuito de site** que avise por e-mail se o endereço sair do ar. Reinstalar leva uns 10 minutos.
4. **A região de origem não muda depois** de criada a conta: escolha *Brazil East (São Paulo)* ou a mais próxima.
5. Não faça *upgrade* para conta paga sem querer: o que passar do limite gratuito passa a ser cobrado.

> O instalador e a imagem são testados automaticamente pelo GitHub Actions (x86 e **ARM**, que é o tipo da máquina grátis da Oracle), mas **ainda não foram
> executados em um servidor real de nenhum provedor**. Se algo falhar, a mensagem na tela diz o passo; guarde o texto.

## Passo a passo

### 1. Criar o servidor
**Opção A, Oracle Cloud:**
1. Entre em **oracle.com/cloud/free** > *Start for free* e crie a conta. O cartão e os dados pessoais **você mesmo digita** no site da Oracle
   (a Oracle pode fazer uma cobrança pequena de verificação, devolvida em seguida).
2. No console: **menu ☰ > Compute > Instances > Create instance**.
   - *Name*: `outgpt`.
   - *Image*: **Canonical Ubuntu 24.04** (a versão ARM, se perguntar).
   - *Shape*: **Change shape > Ampere > VM.Standard.A1.Flex**, **2 OCPU e 12 GB** (se faltar capacidade: 1 OCPU e 6 GB). Procure o selo *Always Free-eligible*.
   - *Networking*: deixe o padrão e marque **Assign a public IPv4 address**.
   - *SSH keys*: **Generate a key pair for me** > **Save private key** (guarde bem o arquivo `.key`; sem ele você não entra no servidor).
   - Clique em **Create**. Quando ficar *Running*, copie o **Public IP address**. Não precisa abrir nenhuma porta.

**Opção B, VPS pago:** contrate um com Ubuntu 22.04/24.04 e 2 GB de RAM; anote o IP e a senha de `root` (ou cadastre sua chave SSH).

### 2. Feche o túnel do seu PC
Se o `PUBLICAR.bat` estiver aberto, feche as duas janelas. Dois computadores no mesmo túnel dividem os visitantes, e uns caem na cópia velha do seu PC.

### 3. Copie as credenciais do túnel
No seu Windows, em um PowerShell. É o arquivo que o `PUBLICAR.bat` criou; o comando copia o conteúdo para a área de transferência:
```powershell
Get-ChildItem "$env:USERPROFILE\.cloudflared\*-*-*-*-*.json" | Get-Content | Set-Clipboard
```
Esse conteúdo é **secreto** (quem o tiver controla o seu túnel): não envie para ninguém nem publique.

### 4. Conecte no servidor e rode o instalador
No PowerShell do Windows (troque `IP-DO-SERVIDOR` e o caminho da chave):
```powershell
# Oracle (usuário "ubuntu"; o 1º comando tira as permissões extras da chave, exigência do SSH do Windows):
icacls "C:\caminho\ssh-key.key" /inheritance:r /grant:r "$($env:USERNAME):R"
ssh -i "C:\caminho\ssh-key.key" ubuntu@IP-DO-SERVIDOR

# VPS pago (usuário "root"):
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

### 5. Primeiro acesso
Abra `https://outgpt.ramosys.com.br`, informe a senha mostrada pelo instalador na tela **Primeiro acesso** e crie o seu login de dono (master).
Em **Administração > Inteligência artificial**, confirme "Conexão ok".

## Usar com outras pessoas
- Não existe cadastro aberto: você cria os acessos em **Usuários** e passa o e-mail e uma senha provisória (a pessoa troca em **Minha senha**).
- Crie uma empresa em **Empresas** e carregue os conteúdos em **Biblioteca** (arquivos TXT, MD, PDF, DOCX ou CSV).
- A página pública de pesquisa (`/pesquisa.html`) continua aberta para qualquer pessoa; os resultados são só do master.

## Custos da IA (importante)
Cada pergunta respondida é uma chamada paga na **sua** chave, feita por qualquer usuário. Antes de divulgar:
1. No console da Anthropic (console.anthropic.com), defina um **limite mensal de gasto** para a chave.
2. Para gastar bem menos, use o modelo menor: `nano /opt/outgpt/.env`, troque para `OUTGPT_MODELO=claude-haiku-5-5` e rode `cd /opt/outgpt && sudo docker compose up -d`.
3. O sistema já limita **20 perguntas por minuto por usuário**.

## Manutenção
| Tarefa | Comando (no servidor) |
|---|---|
| Atualizar para a versão nova do GitHub | `sudo sh /opt/outgpt/servidor/instalar.sh` (mantém banco, logins e configurações) |
| Ver o que está acontecendo | `cd /opt/outgpt && sudo docker compose logs --tail 50 outgpt` (ou `cloudflared`) |
| Reiniciar | `cd /opt/outgpt && sudo docker compose restart` |
| Backup | Automático todo dia às 03:17 (14 cópias, dentro do volume). **Copie para fora do servidor** toda semana: `cd /opt/outgpt && sudo docker compose cp outgpt:/data/backups ./copia-backups` e baixe a pasta com `scp -i "C:\caminho\ssh-key.key" -r ubuntu@IP-DO-SERVIDOR:/opt/outgpt/copia-backups .` |
| Trocar o túnel | `sudo python3 /opt/outgpt/servidor/instalar.py --trocar-tunel` |

Segurança do servidor: nenhuma porta do sistema fica aberta na internet (só o túnel conversa com ele). A única porta exposta é a do SSH: guarde bem a chave
e mantenha o Ubuntu atualizado (`sudo apt update && sudo apt upgrade`). Sobre LGPD e a privacidade dos dados enviados à IA, veja
"Cuidados antes de abrir para outras pessoas" no [DEPLOY.md](DEPLOY.md).

## Se algo der errado
| Sintoma | O que fazer |
|---|---|
| Oracle: "Out of host capacity" | Tente outro *Availability Domain*, 1 OCPU / 6 GB, ou repita mais tarde (pode levar horas ou dias em horários concorridos). |
| `ssh`: "UNPROTECTED PRIVATE KEY FILE" | Rode o comando `icacls` do passo 4. |
| `ssh`: "Permission denied (publickey)" | Usuário errado (Oracle: `ubuntu`; VPS comum: `root`) ou chave de outro servidor. |
| `apt` "Could not get lock" | O servidor ainda terminava o primeiro boot; o instalador espera até 5 minutos. Se persistir, aguarde e rode de novo. |
| "Não consegui ler as credenciais do túnel" | Refaça o passo 3 e cole de novo (o texto começa com `{"AccountTag"`). |
| Instalador diz que o sistema não respondeu | Veja o log mostrado na tela; com menos de 2 GB de RAM a instalação pode travar. |
| Erro 1033 no site | O túnel não conectou: `sudo docker compose logs --tail 30 cloudflared`. Confirme que o túnel do PC está fechado e que o domínio é o mesmo do túnel. |
| Erro 403 ao entrar ("Origem não permitida") | O endereço aberto é diferente do informado no instalador. Rode-o de novo com o endereço certo. |
| Erro 502 | O túnel está ligado mas o sistema não: `sudo docker compose ps` e `sudo docker compose logs outgpt`. |
| Site fora do ar e a máquina da Oracle aparece *Stopped* | A Oracle pode ter recolhido a máquina ociosa: no console, **Start** (ou crie outra e repita o passo 4; restaure o backup se tiver). |

Os dados que você criou no seu PC (empresa, conteúdos, usuários) **não são copiados**: o servidor começa vazio (com os exemplos, se aceitou). Recarregue os conteúdos pela Biblioteca.
