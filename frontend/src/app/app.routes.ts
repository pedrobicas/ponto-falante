import { Routes } from '@angular/router';

const SUFIXO = ' – Ponto Falante';

export const routes: Routes = [
  {
    path: 'favoritos',
    title: 'Favoritos' + SUFIXO,
    loadComponent: () => import('./features/favoritos/favoritos').then((m) => m.Favoritos),
  },
  {
    path: '',
    pathMatch: 'full',
    title: 'Início' + SUFIXO,
    loadComponent: () => import('./features/inicio/inicio').then((m) => m.Inicio),
  },
  {
    path: 'busca',
    title: 'Buscar ponto ou linha' + SUFIXO,
    loadComponent: () => import('./features/busca/busca').then((m) => m.Busca),
  },
  {
    path: 'ponto/:codigo',
    title: 'Próximos ônibus' + SUFIXO,
    loadComponent: () => import('./features/ponto/ponto').then((m) => m.PontoPage),
  },
  {
    path: 'linha/:letreiro',
    title: 'Paradas da linha' + SUFIXO,
    loadComponent: () => import('./features/linha/linha').then((m) => m.LinhaPage),
  },
  {
    path: 'embarque',
    title: 'Embarque assistido' + SUFIXO,
    loadComponent: () => import('./features/embarque/embarque').then((m) => m.EmbarquePage),
  },
  {
    path: 'assistente',
    title: 'Assistente' + SUFIXO,
    loadComponent: () => import('./features/assistente/assistente').then((m) => m.Assistente),
  },
  {
    path: 'boletim',
    title: 'Boletim de esperas previstas' + SUFIXO,
    loadComponent: () => import('./features/boletim/boletim').then((m) => m.BoletimPage),
  },
  {
    path: 'ajustes',
    redirectTo: 'acessibilidade',
  },
  {
    path: 'acessibilidade',
    title: 'Ajustes de acessibilidade' + SUFIXO,
    loadComponent: () => import('./features/acessibilidade/acessibilidade').then((m) => m.Acessibilidade),
  },
  {
    path: 'sobre',
    title: 'Sobre' + SUFIXO,
    loadComponent: () => import('./features/sobre/sobre').then((m) => m.Sobre),
  },
  {
    path: '**',
    title: 'Página não encontrada' + SUFIXO,
    loadComponent: () => import('./features/sobre/nao-encontrada').then((m) => m.NaoEncontrada),
  },
];
