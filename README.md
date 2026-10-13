# STM-Tour
Projeto criado para a disciplina Laboratório de desenvolvimento de software

A página `/mapa`, aberta após o login do usuário, exibe um mapa interativo de Santarém gerado com Folium e OpenStreetMap. É possível arrastar o mapa e usar os controles de zoom ou o gesto de pinça. Os mapas e recursos do Leaflet precisam de conexão com a internet. Após atualizar as dependências, reconstrua o serviço com `docker compose up -d --build`.

## Painel do administrador

1. Configure o `.env` usando `.env.example` e defina `SECRET_KEY` com uma chave aleatória longa (por exemplo, `openssl rand -hex 32`). Em HTTPS, use `SESSION_COOKIE_SECURE=true`.
2. Inicie ou reconstrua os serviços: `docker compose up -d --build`.
3. Crie o administrador: `docker compose exec web flask --app wsgi create-admin`. O comando solicita e-mail e senha (mínimo de 12 caracteres), com confirmação. A senha é armazenada como hash; não existe senha padrão.
4. Acesse `http://localhost:5000/entrar` ou clique em **Entrar** na página inicial. O login identifica a permissão da conta: administradores seguem para o painel e os demais usuários, para o mapa. Ajuste a porta se tiver alterado `FLASK_PORT`.

O painel permite listar, cadastrar, editar e remover locais com nome, descrição e foto. As fotos são validadas e armazenadas no MongoDB junto ao local; são aceitos JPG, PNG e WebP de até 5 MB e 20 megapixels. Ao editar, é possível manter a foto atual. A remoção exige confirmação. As sessões expiram após oito horas; sem `SECRET_KEY` configurada, uma chave temporária é gerada a cada inicialização.

Para promover uma conta existente, abra **Gerenciar usuários** no painel e clique em **Tornar administrador** na conta desejada. Apenas administradores podem conceder essa permissão. O usuário promovido pode atualizar o perfil e clicar em **Painel administrativo**, sem sair da conta; nos próximos logins, será direcionado ao painel.

Os locais cadastrados diretamente pelo administrador e os novos pontos aprovados aparecem em **Explorar → Pontos turísticos** (`/locais`). O mapa Folium exibe pins dos pontos públicos com coordenadas válidas. Ao clicar, abre um cartão com foto, nome, descrição e link para o local. O enquadramento se ajusta aos pontos; sem pontos, fica centrado em Santarém. Cadastros antigos sem coordenadas continuam na lista e não recebem uma localização automática.

### Contribuições e aprovação

- Usuários conectados podem clicar em **Sugerir novo ponto** e enviar nome, descrição, foto e localização. É possível digitar latitude/longitude em graus decimais (ponto ou vírgula) ou escolher no mapa, clicando ou arrastando o pin.
- Na página de um ponto público, **Enviar foto ou sugerir descrição** permite adicionar uma foto à galeria ou propor uma nova descrição. Cada envio é revisado separadamente.
- **Minhas contribuições**, também disponível no perfil, mostra os estados aguardando aprovação, aprovada e rejeitada.
- No painel, **Revisar contribuições** permite visualizar os envios, comparar descrições e **Aprovar e publicar** ou **Rejeitar**. Somente administradores podem decidir.

Envios pendentes ou rejeitados ficam privados para o autor e os administradores, inclusive suas fotos. Uma descrição proposta só substitui a descrição pública após aprovação; fotos aprovadas são adicionadas à galeria, preservando a foto principal. Novos pontos só aparecem na lista pública e no mapa após aprovação. Atualize o mapa aberto para carregar os pontos recém-aprovados. Cadastros feitos diretamente no painel administrativo continuam sendo publicados imediatamente e também oferecem o seletor de localização. A edição de um cadastro administrativo antigo permite adicionar suas coordenadas.

As contribuições ficam na coleção `contributions`, com autor, data, estado e registro de quem decidiu. A mudança de estado é atômica e aceita apenas uma decisão por envio; a visualização pública consulta somente contribuições aprovadas. Pontos criados pela comunidade ficam nessa coleção e são acessados na lista pública; a edição e remoção do painel de locais continuam voltadas aos cadastros diretos do administrador.

### Testes

Instale `requirements-dev.txt` em um ambiente Python e execute `python -m pytest`. Os testes usam MongoDB simulado, sem alterar o banco do projeto.

## Acesso do usuário

Na página inicial, **Entrar** abre `/entrar`, e **Criar conta** abre `/criar-conta`. O cadastro exige senha de pelo menos 4 caracteres e a armazena como hash no MongoDB. Após autenticação, o usuário é direcionado ao mapa. Contas de usuários comuns só podem acessar o painel após receberem a permissão de administrador. O perfil oferece a opção de sair da conta.

O login é único para todas as contas. Novas contas ficam na coleção `users`, com `role: user` no cadastro público e `role: admin` pelo comando `create-admin`. O servidor consulta a permissão no banco em cada acesso ao painel; usuários sem essa permissão recebem HTTP 403. Administradores também encontram o link **Painel administrativo** no perfil.

Administradores antigos da coleção `admins` continuam entrando pela mesma tela. Se já houver uma conta em `users` com o mesmo e-mail, ela tem prioridade e não recebe privilégios automaticamente. O cadastro e o comando `create-admin` recusam e-mails já utilizados em qualquer uma das coleções. A URL antiga `/admin/entrar` redireciona para `/entrar`.
