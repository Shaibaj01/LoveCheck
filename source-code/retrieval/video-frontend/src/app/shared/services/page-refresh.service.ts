import { Injectable } from '@angular/core';
import { Subject } from 'rxjs';

/** Toolbar refresh / re-click active nav — pages subscribe and reload their own data. */
@Injectable({ providedIn: 'root' })
export class PageRefreshService {
  private readonly refreshSubject = new Subject<void>();
  readonly refresh$ = this.refreshSubject.asObservable();

  requestRefresh(): void {
    this.refreshSubject.next();
  }
}
