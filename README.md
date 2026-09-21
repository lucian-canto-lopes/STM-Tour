# STM-Tour
Projeto criado para a disciplina Laboratório de desenvolvimento de software

A página `/mapa`, aberta após o login do usuário, exibe um mapa interativo de Santarém gerado com Folium e OpenStreetMap. É possível arrastar o mapa e usar os controles de zoom ou o gesto de pinça. Os mapas e recursos do Leaflet precisam de conexão com a internet. Após atualizar as dependências, reconstrua o serviço com `docker compose up -d --build`.

## Painel do administrador

1. Configure o `.env` usando `.env.example` e defina `SECRET_KEY` com uma chave aleatória longa (por exemplo, `openssl rand -hex 32`). Em HTTPS, use `SESSION_COOKIE_SECURE=true`.
2. Inicie ou reconstrua os serviços: `docker compose up -d --build`.
3. Crie o administrador: `docker compose exec web flask --app wsgi create-admin`. O comando solicita e-mail e senha (mínimo de 12 caracteres), com confirmação. A senha é armazenada como hash; não existe senha padrão.
4. Acesse `http://localhost:5000/admin/entrar` ou clique em **Entrar como administrador** na página inicial. Ajuste a porta se tiver alterado `FLASK_PORT`.

O painel permite listar, cadastrar, editar e remover locais com nome, descrição e foto. As fotos são validadas e armazenadas no MongoDB junto ao local; são aceitos JPG, PNG e WebP de até 5 MB e 20 megapixels. Ao editar, é possível manter a foto atual. A remoção exige confirmação. As sessões expiram após oito horas; sem `SECRET_KEY` configurada, uma chave temporária é gerada a cada inicialização.

Os locais cadastrados são exibidos no painel administrativo. As telas públicas de mapa e local continuam com os exemplos existentes.

### Testes

Instale `requirements-dev.txt` em um ambiente Python e execute `python -m pytest`. Os testes usam MongoDB simulado, sem alterar o banco do projeto.

## Acesso do usuário

Na página inicial, **Entrar como usuário** abre `/entrar`, e **Criar conta** abre `/criar-conta`. O cadastro exige senha de pelo menos 4 caracteres e a armazena como hash no MongoDB. Após autenticação, o usuário é direcionado ao mapa. Contas de usuários não permitem acessar o painel administrativo. O perfil oferece a opção de sair da conta.
