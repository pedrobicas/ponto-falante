import { Routes } from '@angular/router';

const SUFIXO = ' – Ponto Falante';

export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    title: 'Início' + SUFIXO,
    loadComponent: () => import('./features/inicio/inicio').then((m) => m.Inicio),
  },
  {
    path: 'ponto/:codigo',
    title: 'Próximos ônibus' + SUFIXO,
    loadComponent: () => import('./features/ponto/ponto').then((m) => m.PontoPage),
  },
  {
    path: 'assistente',
    title: 'Assistente' + SUFIXO,
    loadComponent: () => import('./features/assistente/assistente').then((m) => m.Assistente),
  },
  {
    path: 'boletim',
    title: 'Boletim de atrasos' + SUFIXO,
    loadComponent: () => import('./features/boletim/boletim').then((m) => m.BoletimPage),
  },
  {
    path: 'acessibilidade',
    title: 'Acessibilidade' + SUFIXO,
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
