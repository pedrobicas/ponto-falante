import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';
import { ErroApi } from './models';

export function mensagemParaStatus(status: number, corpo?: unknown): string {
  const doServidor =
    corpo && typeof corpo === 'object' && typeof (corpo as { mensagem?: unknown }).mensagem === 'string'
      ? (corpo as { mensagem: string }).mensagem
      : null;
  switch (status) {
    case 0:
      return 'Não consegui falar com o servidor. Verifique a internet e tente de novo.';
    case 400:
      return doServidor ?? 'O pedido não está correto. Confira o que você digitou.';
    case 404:
      return doServidor ?? 'Não encontramos o que você procurou.';
    case 429:
      return 'Muitas tentativas seguidas. Espere um minuto e tente de novo.';
    case 503:
      return doServidor ?? 'O serviço da SPTrans não está respondendo agora.';
    default:
      return 'Algo deu errado do nosso lado. Tente de novo em instantes.';
  }
}

/** Converte qualquer falha HTTP em ErroApi com mensagem simples em português. */
export const erroHttpInterceptor: HttpInterceptorFn = (req, next) =>
  next(req).pipe(
    catchError((e: unknown) => {
      if (e instanceof HttpErrorResponse) {
        const corpo = e.error as { codigo?: string } | null;
        return throwError(() => new ErroApi(e.status, mensagemParaStatus(e.status, e.error), corpo?.codigo));
      }
      return throwError(() => new ErroApi(-1, mensagemParaStatus(-1)));
    }),
  );
