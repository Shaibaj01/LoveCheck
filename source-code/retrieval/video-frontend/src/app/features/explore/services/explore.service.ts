import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import {
  ExploreResponse,
  VideoScope,
  VideoSynthesizeRequest,
  VideoSynthesizeResponse,
} from '../../../shared/models/video.model';

@Injectable({ providedIn: 'root' })
export class ExploreService {
  private http = inject(HttpClient);

  explore(params: {
    scope: VideoScope;
    date?: string | null;
    limit?: number;
    offset?: number;
  }): Observable<ExploreResponse> {
    let httpParams = new HttpParams()
      .set('scope', params.scope)
      .set('limit', String(params.limit ?? 48))
      .set('offset', String(params.offset ?? 0));
    if (params.date) {
      httpParams = httpParams.set('date', params.date);
    }
    return this.http.get<ExploreResponse>(`${environment.apiUrl}/videos/explore`, {
      params: httpParams,
    });
  }

  synthesize(body: VideoSynthesizeRequest): Observable<VideoSynthesizeResponse> {
    return this.http.post<VideoSynthesizeResponse>(
      `${environment.apiUrl}/videos/synthesize`,
      body
    );
  }
}
