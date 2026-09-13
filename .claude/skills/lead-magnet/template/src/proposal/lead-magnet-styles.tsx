/** The cold report's finish is isolated from the shared contract styles. */
export function LeadMagnetStyles() {
  return <style>{`
/* ---------------------------------------------------------- Schriftskala ---
 * VIER ROLLEN, NICHT SIEBEN GROESSEN (the reviewer, 06.09.2026: „einheitliche Fonts und
 * Ueberschriftengroessen festlegen"). Vorher trug jede Sektion ihre eigene
 * clamp-Formel: 76, 58, 48, 44, 36, 30, 26 Pixel, keine zwei gleich und keine
 * aus einer Reihe. Deshalb las sich eine Ueberschrift ueber einer Liste so
 * gross wie die Aussage im Hero.
 *
 * Die Rolle entscheidet, nicht das Gefuehl beim Bauen:
 *   hero     einmal je Seite, der Satz auf den alles zulaeuft
 *   aussage  eine Sektion behauptet etwas (Verlust, Loesung, Plan, Abschluss)
 *   sektion  ordnet einen Block, behauptet nichts (Scorecard, Saeulen)
 *   block    fuehrt eine Liste an (Jetzt beheben, ein Schritt der Loesung)
 *
 * Je groesser die Schrift, desto enger laeuft sie: was bei 20px richtig sitzt,
 * faellt bei 68px auseinander. Deshalb gehoert die Laufweite an die Stufe und
 * wird nicht je Stelle geraten. */
.lm-report{
 --lm-hero:clamp(42px,5vw,68px);      --lm-hero-lw:-.055em; --lm-hero-zh:1.0;
 --lm-aussage:clamp(28px,3.2vw,44px); --lm-aussage-lw:-.042em; --lm-aussage-zh:1.06;
 --lm-sektion:clamp(21px,2.1vw,28px); --lm-sektion-lw:-.032em; --lm-sektion-zh:1.15;
 --lm-block:clamp(18px,1.6vw,22px);   --lm-block-lw:-.025em; --lm-block-zh:1.2;
 /* ARCHIVO, WIE DER REST DER MARKE (the reviewer, 06.09.2026, Entscheidung an mich
    delegiert). Der Bericht lief auf Inter, das Verkaufsdokument und der Vertrag
    auf Archivo: derselbe Interessent sah zwei Schriften auf dem Weg vom
    Kaltkontakt zur Unterschrift. Dazu ist Inter die Schrift, an der man
    erzeugte Seiten erkennt, und ein Kaltreport lebt davon, echt zu wirken.
    Archivo ist bereits im Layout eingebettet (app/fonts.css, alle Schnitte
    von 400 bis 900, font-display: swap), kostet also keinen neuen Request. */
 background:var(--color-canvas);font-family:var(--font-core),var(--font-sans),sans-serif}
.lm-report h1,.lm-report h2,.lm-report h3{text-wrap:balance;font-weight:700}
/* ------------------------------------------------ Kapitel und Bloecke ---
 * Jedes Kapitel traegt denselben Kopf (Nummer, Name, Aussage), jeder Block
 * darin dieselbe kleine Marke. Vorher hatte von fuenf Abschnitten genau einer
 * eine Marke, und die Ueberschriften standen sonst nackt da - man sah eine
 * Folge von Aussagen statt einen Bericht mit Kapiteln (the reviewer, 06.09.2026). */
.lm-kopf+*{margin-top:32px}

/* VIER ROLLEN FUER KLEINSCHRIFT, NICHT NEUN VARIANTEN. Gemessen am 06.09.2026
   trugen die Marken im Bericht 9, 9.5, 10 und 10.5 Pixel, die Gewichte 600, 700
   und 900 und Laufweiten von 0.2 bis 1.4 Pixel - jede Stelle hatte ihre eigenen
   Werte, weil sie einzeln getippt wurden. Vier Rollen reichen, und welche gilt,
   entscheidet die Aufgabe:
     kapitelmarke  Nummer und Kapitelname, einmal je Kapitel
     blockmarke    fuehrt einen Block innerhalb eines Kapitels an
     spaltenkopf   benennt eine Tabellenspalte
     datenlabel    beschriftet einen Wert (Score, Paket, Dauer) */
.lm-report .lm-kapitelmarke{font-size:10.5px;font-weight:900;text-transform:uppercase;letter-spacing:.13em}
.lm-report .lm-blockmarke{font-size:10px;font-weight:900;text-transform:uppercase;letter-spacing:.11em;color:var(--color-navy)}
.lm-report .lm-spaltenkopf{font-size:9.5px;font-weight:900;text-transform:uppercase;letter-spacing:.08em;color:var(--color-graphite)}
.lm-report .lm-datenlabel{font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--color-pewter)}
.lm-blockmarke+*{margin-top:14px}

/* Fuer Ueberschriften, die im JSX statt hier stehen: dieselbe Stufe, eine Klasse. */
.lm-report .lm-h-aussage{font-size:var(--lm-aussage);line-height:var(--lm-aussage-zh);letter-spacing:var(--lm-aussage-lw)}
.lm-report .lm-h-sektion{font-size:var(--lm-sektion);line-height:var(--lm-sektion-zh);letter-spacing:var(--lm-sektion-lw)}
.lm-report .lm-h-block{font-size:var(--lm-block);line-height:var(--lm-block-zh);letter-spacing:var(--lm-block-lw)}

/* ------------------------------------ Bewegung in der Verlust-Sektion ---
 * Dieselbe Machart wie unten im Loesungsteil (the reviewer, 06.09.2026: „genauso wie am
 * Ende des Lead Magnets"): nur transform, opacity und stroke-dashoffset, damit
 * der Browser nichts neu berechnen muss. Jede beginnt in ihrem Endzustand, so
 * dass ein stehendes Bild vollstaendig ist - wer Bewegung abgestellt hat, sieht
 * dieselbe Zeichnung, nur still. */
.lm-losses .laeuft{stroke-dasharray:3 9;animation:lm-l-laeuft 2.4s linear infinite}
@keyframes lm-l-laeuft{to{stroke-dashoffset:-24}}
.lm-losses .fuellt{stroke-dasharray:230;stroke-dashoffset:0;animation:lm-l-fuellt 5.5s cubic-bezier(.45,0,.25,1) infinite}
@keyframes lm-l-fuellt{0%{stroke-dashoffset:230}35%,100%{stroke-dashoffset:0}}
.lm-losses .tickt{transform-origin:164px 66px;animation:lm-l-tickt 5.5s cubic-bezier(.5,0,.2,1) infinite}
@keyframes lm-l-tickt{0%,6%{transform:rotate(0)}94%,100%{transform:rotate(360deg)}}
.lm-losses .pocht{animation:lm-l-pocht 3s ease-in-out infinite}
@keyframes lm-l-pocht{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.65;transform:scale(.88)}}
.lm-losses .rutscht{animation:lm-l-rutscht 4.5s ease-in-out infinite}
@keyframes lm-l-rutscht{0%,100%{transform:translateX(0)}50%{transform:translateX(5px)}}
@media (prefers-reduced-motion: reduce){
 .lm-losses .laeuft,.lm-losses .fuellt,.lm-losses .tickt,
 .lm-losses .pocht,.lm-losses .rutscht{animation:none}
}
.lm-report :is(button,a,[role=button],summary):focus-visible{outline:3px solid var(--color-navy);outline-offset:4px}
.lm-report header nav{min-height:88px;border-color:var(--color-hairline)}
.lm-hero{padding-top:64px;padding-bottom:64px;background:linear-gradient(150deg,var(--color-surface),var(--color-canvas) 72%)}
.lm-hero>div[aria-hidden]{display:none}
.lm-hero>div.relative{row-gap:40px}
.lm-hero h1{max-width:12ch;font-size:var(--lm-hero);line-height:var(--lm-hero-zh);letter-spacing:var(--lm-hero-lw);margin-top:28px}
.lm-hero [data-onepager=hook]{font-weight:500;line-height:1.55;margin-top:24px;max-width:44ch;color:var(--color-graphite)}
/* Gilt dem Videorahmen im Hero, nicht jedem figure darin: der Belegstreifen
   nutzt ebenfalls figure, und seine Sternezeile bekam dadurch einen Rahmen
   quer durch die Karte (07.09.2026). */
.lm-hero figure:not(.lm-beleg-karte)>div{border:1px solid color-mix(in srgb,var(--color-navy-deep) 20%,transparent);border-radius:24px;box-shadow:var(--shadow-raised)}
.lm-hero article{padding:22px 24px;border-color:var(--color-hairline)}
.lm-hero article>span{width:44px;height:44px;border-radius:13px;background:var(--color-navy-soft);box-shadow:inset 0 1px 0 #ffffffb3}
.lm-hero article svg{width:25px;height:25px;stroke-width:1.65}
.lm-hero article strong{font-size:14px;font-weight:600;line-height:1.4}
.lm-analysis{background:var(--color-surface-2);padding-top:72px;padding-bottom:80px;border-color:var(--color-hairline)}
.lm-actions{margin-top:0}
/* Die Ueberschrift fuehrt eine Liste an, sie behauptet nichts (the reviewer, 06.09.2026:
   „unproportional gross"). Vorher stand sie mit 42px so gross da wie die Aussagen
   im Hero und in der Verlust-Sektion. */
.lm-actions h2{font-size:var(--lm-block);line-height:var(--lm-block-zh);letter-spacing:var(--lm-block-lw)}
.lm-actions>div{margin-top:18px;border-radius:20px;border-color:var(--color-hairline);box-shadow:var(--shadow-card)}
.lm-actions>div>div:first-child{padding:11px 26px;background:var(--color-canvas);column-gap:20px}
/* Die Zeilen waren fuer zwei Textzeilen 25px hoch gepolstert und standen damit
   halb leer. Enger gesetzt liest sich die Liste als Liste. */
.lm-actions article{padding:16px 26px;column-gap:20px;border-color:var(--color-hairline)}
.lm-actions article:hover{background:#fbfaf7}
.lm-actions article>b{background:var(--color-canvas);color:var(--color-graphite);border:1px solid #0000001a;width:24px;height:24px;font-size:11px}
.lm-actions article p{font-size:15px;font-weight:500;line-height:1.5}
.lm-actions article>div:last-child>p{font-weight:600}
.lm-actions summary{font-size:10px;min-height:26px;letter-spacing:.06em}
/* Der Pfeil rueckt beim Ueberfahren der Zeile ein Stueck in Richtung Loesung und
   wird dabei kraeftiger: dieselbe Bewegung, die der Satz beschreibt. Nur transform
   und color, damit nichts neu umbricht. */
.lm-actions .lm-pfeil{transition:color 200ms cubic-bezier(.23,1,.32,1),transform 200ms cubic-bezier(.23,1,.32,1)}
@media (hover:hover) and (pointer:fine){
 .lm-actions article:hover .lm-pfeil{color:var(--color-navy);transform:translateX(3px)}
}
@media (prefers-reduced-motion:reduce){
 .lm-actions .lm-pfeil{transition:none}
 .lm-actions article:hover .lm-pfeil{transform:none}
}
/* Bleistift auf Papier: der Rahmen liegt in der Tintenfarbe, aber schwach, und
   zieht beim Ueberfahren an. Kein Schatten - eine Zeichnung wirft keinen. */
.lm-beleg-karte{color:rgba(28,22,14,.82)}
.lm-beleg-karte svg,.lm-beleg .lm-marke{transition:color 200ms cubic-bezier(.23,1,.32,1),border-color 200ms cubic-bezier(.23,1,.32,1)}
@media (hover:hover) and (pointer:fine){
 .lm-beleg-karte:hover{color:rgba(28,22,14,1)}
 .lm-beleg .lm-marke:hover{border-color:var(--color-hairline-strong)}
}
@media (prefers-reduced-motion:reduce){
 .lm-beleg-karte svg,.lm-beleg .lm-marke{transition:none}
}
.lm-analysis section[aria-label]{margin-bottom:64px}
.lm-scorecard{border-color:var(--color-hairline);border-radius:26px;box-shadow:var(--shadow-raised)}
.lm-scorecard>div:first-child{padding:28px 36px;background:linear-gradient(120deg,var(--color-navy-deep),var(--color-navy));gap:16px}
.lm-scorecard>div:first-child h2{font-size:var(--lm-sektion);line-height:var(--lm-sektion-zh);letter-spacing:var(--lm-sektion-lw)}
.lm-scorecard>div:first-child>strong{color:var(--color-surface);font-weight:600}
.lm-scorecard>div:first-child small{color:var(--color-on-navy-muted)}
.lm-pillar>button{padding:28px 32px;border-left-width:0;column-gap:24px;transition:none;background:var(--color-surface)}
.lm-pillar>button:hover{background:var(--color-surface-2)}
.lm-pillar>button[aria-expanded=true]{background:var(--color-navy-soft)}
.lm-pillar>button>span:first-child{font-weight:500;color:var(--color-pewter)}
.lm-pillar h2{font-size:var(--lm-sektion);line-height:var(--lm-sektion-zh);letter-spacing:var(--lm-sektion-lw)}
.lm-pillar [data-onepager=pillar]{font-size:9.5px;font-weight:700;letter-spacing:.08em;line-height:1.5}
.lm-pillar>div[id]{padding:32px;border-left-width:0;background:var(--color-canvas);border-color:var(--color-hairline)}
.lm-pillar li{line-height:1.6}
.lm-pillar button>div:last-child>span{min-width:120px;font-weight:600;font-size:13px;box-shadow:var(--shadow-xs)}
.lm-score{min-width:116px;padding:14px 18px;border-radius:16px;border-color:transparent;font-weight:600;box-shadow:inset 0 1px 0 #ffffffb3}
.lm-score>small{font-size:9.5px;opacity:.8;font-weight:700;letter-spacing:.08em}
.lm-score>span{font-size:38px;font-weight:600}
.lm-offer{margin-top:32px;padding:24px;background:var(--color-navy-soft);border-color:transparent;border-radius:20px}
.lm-offer>div>button{padding:18px 14px;gap:12px;border-color:var(--color-hairline);border-radius:14px;box-shadow:var(--shadow-xs)}
.lm-offer button[aria-expanded=true]{background:linear-gradient(135deg,var(--color-navy),var(--color-navy-deep));border-color:var(--color-navy)}
.lm-offer button>span:first-child{width:40px;height:40px;border-radius:12px;background:var(--color-navy-soft);color:var(--color-navy)}
.lm-offer button>span:first-child svg{stroke:currentColor;width:24px;height:24px}
.lm-offer button b{font-weight:600;line-height:1.4}
.lm-offer p{line-height:1.6}
.lm-report>section.lm-plan{margin-top:72px;margin-bottom:80px}
.lm-plan h2{font-size:var(--lm-aussage);letter-spacing:var(--lm-aussage-lw);line-height:var(--lm-aussage-zh)}
.lm-plan [role=tablist]{margin-top:28px;margin-bottom:28px;gap:6px;padding:5px;border-radius:16px;background:var(--color-panel)}
.lm-plan [role=tab]{border:0;border-radius:12px;padding:12px 20px;font-weight:600}
.lm-plan [role=tab][aria-selected=true]{background:linear-gradient(130deg,var(--color-navy),var(--color-navy-deep));box-shadow:var(--shadow-card)}
.lm-plan [role=tab][aria-selected=false]{background:transparent}
.lm-gantt>div:first-child{padding-bottom:14px}
.lm-gantt [role=button]{padding-top:17px;padding-bottom:17px;min-height:64px}
.lm-gantt [role=button]:hover,.lm-gantt [role=button][aria-expanded=true]{background:var(--color-surface-2)}
.lm-gantt [role=button]>span:first-child{align-items:center;line-height:1.5}
.lm-gantt .size-6{width:34px;height:34px;border-radius:10px}
.lm-gantt .size-6 svg{width:21px;height:21px}
.lm-gantt .font-mono{font-family:inherit;font-size:10px;letter-spacing:.025em}
.lm-mobile-plan>div{border-radius:18px;box-shadow:var(--shadow-card)}
.lm-mobile-plan button{padding:14px 12px;min-height:64px;column-gap:10px}
.lm-mobile-plan button>b{font-size:12px;line-height:1.45;font-weight:600}
.lm-mobile-plan button>span:first-child{width:26px;height:30px;border-radius:8px}
.lm-mobile-plan button>span:first-child svg{width:19px;height:19px}
.lm-mobile-plan [data-grow].bg-navy{background:linear-gradient(90deg,var(--color-navy),var(--color-navy-deep))}
.lm-close{border-top:0;padding-top:64px;padding-bottom:64px;background:linear-gradient(135deg,var(--color-navy-deep),var(--color-navy) 180%)}
.lm-close h2{font-size:var(--lm-aussage);line-height:var(--lm-aussage-zh);letter-spacing:var(--lm-aussage-lw)}
.lm-close>div>div:first-child{margin-bottom:32px}
.lm-close aside{border-radius:22px;box-shadow:var(--shadow-raised)}
.lm-close aside>div:first-child{padding:24px}
.lm-report>footer{background:var(--color-canvas);padding-top:32px;padding-bottom:32px}
/* Only the one-shot observer explains changes; hover and repeat visits are still. */
.lm-report *{transition:none}
@media(max-width:639px){
 .lm-report header nav{min-height:70px;gap:12px}
 .lm-hero{padding-top:36px;padding-bottom:40px}
 .lm-hero h1{font-size:49px;max-width:11ch;margin-top:24px}
 .lm-hero [data-onepager=hook]{font-size:17px;line-height:1.5;margin-top:20px}
 .lm-hero>div.relative{gap:28px}
 .lm-hero article{padding:15px 18px}
 .lm-hero article>span{width:36px;height:36px;border-radius:10px}
 .lm-hero article svg{width:22px;height:22px}
 .lm-analysis{padding-top:44px;padding-bottom:44px}
 .lm-actions>div{margin-top:22px;border-radius:18px}
 .lm-actions article{padding:15px 16px;column-gap:12px;row-gap:8px}
 .lm-actions article p{font-size:14px;line-height:1.6}
 .lm-analysis section[aria-label]{margin-bottom:40px}
 .lm-scorecard{border-radius:20px}
 .lm-scorecard>div:first-child{padding:24px 20px}
 .lm-scorecard>div:first-child>strong{font-size:46px}
 .lm-pillar>button{padding:24px 18px;column-gap:12px;grid-template-columns:22px minmax(0,1fr) auto}
 .lm-pillar h2{font-size:24px;line-height:1.1}
 .lm-pillar>button>div:nth-child(2){grid-column:2 / -1;grid-row:1}
 .lm-pillar>button>div:last-child{grid-row:2;grid-column:3}
 .lm-score{min-width:106px;padding:12px 14px}
 .lm-score>span{font-size:32px}
 .lm-pillar button>div:last-child>span{min-width:104px;padding:0 14px;font-size:12px}
 .lm-pillar>div[id]{padding:20px 12px}
 .lm-offer{padding:18px 14px;margin-top:24px}
 .lm-offer>div>button{padding:14px}
 .lm-report>section.lm-plan{margin-top:44px;margin-bottom:48px}
 .lm-plan [role=tablist]{gap:3px;margin:24px 0 20px}
 .lm-plan [role=tab]{padding:12px 6px}
 .lm-close{padding-top:44px;padding-bottom:100px}
}
@media(prefers-reduced-motion:reduce){.lm-report *,.lm-report *::before,.lm-report *::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}}

/* ORANGE IST DER AKZENT, NAVY BLEIBT DIE HANDLUNG (the reviewer, 06.09.2026).
   Der Report war durchgehend navy auf Creme - sauber, aber ohne Blick­fang, und die
   Hausfarbe Orange (--color-orange) kam gar nicht vor. Die Regel dahinter, damit es nicht
   bunt wird: Orange markiert, wohin man schauen soll (Ziffern, Kicker, geöffnete Zeile),
   Navy bleibt für alles, was man anklickt. Ein Knopf wird nie orange. */
.lm-report{--lm-accent:var(--color-orange);--lm-accent-soft:var(--color-orange-soft)}
.lm-report [class*="text-navy"]:is(p,span,b):not(button *):not(a *){}
.lm-hero{background:
  radial-gradient(120% 90% at 88% -10%,color-mix(in srgb,var(--lm-accent) 12%,transparent),transparent 60%),
  linear-gradient(150deg,var(--color-surface),var(--color-canvas) 72%)}
.lm-hero>div.relative>div:first-child>span:first-child{border-color:color-mix(in srgb,var(--lm-accent) 35%,transparent)}
/* Der Kicker bekommt einen kurzen Strich in Orange: er führt das Auge in den Abschnitt,
   ohne dass eine ganze Fläche die Farbe trägt. */
/* Der Strich stand ueber "Jetzt beheben", als das noch eine Sektion anfuehrte.
   Seit dem Kapitel-Umbau ist es eine Ueberschrift INNERHALB von Kapitel 02, und
   der Strich doppelte dort die Kapitelmarke ein paar Zeilen darueber. Er bleibt
   nur, wo er eine Sektion anfuehrt. */
.lm-plan p:first-child::before{content:"";display:block;width:34px;height:3px;border-radius:2px;margin-bottom:14px;
  background:linear-gradient(90deg,var(--lm-accent),color-mix(in srgb,var(--lm-accent) 25%,transparent))}
.lm-actions article>b{background:linear-gradient(140deg,var(--lm-accent),color-mix(in srgb,var(--lm-accent) 72%,#7a2d00));color:#fff;
  box-shadow:0 1px 2px color-mix(in srgb,var(--lm-accent) 45%,transparent)}
/* KORREKTUR 06.09.2026: hier stand Orange, und damit widersprach diese Zeile dem
   Kommentar drei Zeilen darueber („Navy bleibt fuer alles, was man anklickt").
   „Details" und „2 weitere anzeigen" sind Aufklapper, also Navy. Orange bleibt bei
   den Ziffern und dem Kicker-Strich, die nur markieren, und beim Handlungsknopf. */
.lm-actions summary{color:var(--color-navy)}
.lm-scorecard>div:first-child{background:
  radial-gradient(90% 200% at 100% 0,color-mix(in srgb,var(--lm-accent) 34%,transparent),transparent 55%),
  linear-gradient(120deg,var(--color-navy-deep),var(--color-navy))}
.lm-pillar>button[aria-expanded=true]{box-shadow:inset 3px 0 0 var(--lm-accent)}
.lm-pillar>button>span:first-child{color:color-mix(in srgb,var(--lm-accent) 70%,var(--color-pewter))}
.lm-offer{background:
  linear-gradient(155deg,color-mix(in srgb,var(--lm-accent) 9%,var(--color-navy-soft)),var(--color-navy-soft) 65%)}
.lm-offer>p:first-child{color:color-mix(in srgb,var(--lm-accent) 74%,#2a1400)}
.lm-plan [role=tab][aria-selected=true]{box-shadow:var(--shadow-card),inset 0 -2px 0 var(--lm-accent)}
.lm-gantt [role=button][aria-expanded=true]{box-shadow:inset 3px 0 0 var(--lm-accent)}
.lm-close{background:
  radial-gradient(80% 120% at 12% 0,color-mix(in srgb,var(--lm-accent) 26%,transparent),transparent 58%),
  linear-gradient(135deg,var(--color-navy-deep),var(--color-navy) 180%)}
.lm-report>footer>div>span:first-child>b{background:linear-gradient(140deg,var(--color-navy),var(--color-navy-deep))}
.lm-report header nav>span:first-child>b{background:linear-gradient(140deg,var(--color-navy),var(--color-navy-deep));
  box-shadow:0 1px 0 color-mix(in srgb,var(--lm-accent) 40%,transparent)}
/* Der Knopf antwortet auf den Druck: 160 ms, ease-out, ein Hauch kleiner. Ohne das fühlt
   sich ein Klick an, als hätte die Seite ihn nicht gehört. */
/* DER KNOPF IST DAS EINZIGE ORANGE AUF DER SEITE (the reviewer, 06.09.2026). Der ganze Bericht
   laeuft in Navy und Sand; wenn genau eine Flaeche die Signalfarbe traegt, findet das Auge
   sie ohne Suchen. Wuerde Orange auch anderswo stehen, waere es Dekoration statt Wegweiser.

   Drei Schichten, jede mit einem Zweck: der Verlauf gibt Tiefe (eine flache Flaeche wirkt
   gedruckt), der Schimmer laeuft alle fuenf Sekunden einmal durch und holt den Blick zurueck,
   ohne zu blinken, und der Schatten traegt dieselbe Farbe wie der Knopf statt Grau -- ein
   grauer Schatten unter einer warmen Flaeche sieht schmutzig aus.

   Der Schimmer ist bewusst langsam und weit auseinander. Ein pulsierender Knopf wirkt wie
   ein Werbebanner, und der Bericht lebt davon, dass er nicht nach Werbung aussieht. */
.lm-report .lm-cta{position:relative;overflow:hidden;
  background:linear-gradient(135deg,
    color-mix(in oklab,var(--color-orange) 88%,white) 0%,
    var(--color-orange) 46%,
    color-mix(in oklab,var(--color-orange) 86%,black) 100%) !important;
  color:#fff !important;
  transition:transform 160ms cubic-bezier(.23,1,.32,1),box-shadow 160ms cubic-bezier(.23,1,.32,1),filter 160ms;
  box-shadow:0 1px 2px color-mix(in srgb,var(--color-orange) 30%,transparent),
             0 8px 20px -6px color-mix(in srgb,var(--color-orange) 55%,transparent)}
.lm-report .lm-cta::after{content:"";position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(105deg,transparent 38%,rgba(255,255,255,.42) 50%,transparent 62%);
  transform:translateX(-130%);animation:lm-schimmer 5s ease-in-out 1.5s infinite}
@keyframes lm-schimmer{0%,72%{transform:translateX(-130%)}100%{transform:translateX(130%)}}
.lm-report .lm-cta:active{transform:scale(.97)}
@media (hover:hover) and (pointer:fine){
  .lm-report .lm-cta:hover{filter:brightness(1.06);
    box-shadow:0 2px 6px color-mix(in srgb,var(--color-orange) 34%,transparent),
               0 14px 30px -8px color-mix(in srgb,var(--color-orange) 62%,transparent)}
}
@media (prefers-reduced-motion: reduce){
  .lm-report .lm-cta{transition:none}
  .lm-report .lm-cta::after{animation:none;opacity:0}
}

/* GLAS STATT FLÄCHE (the reviewer, 06.09.2026: „cooler glasy look wie bei Apple").
   Drei Schichten machen den Unterschied: ein Verlauf von fast weiss nach blau, eine
   helle Kante innen an der Oberseite, und ein weicher Schatten darunter. Der Verlauf
   allein sieht flach aus, die Kante allein sieht aufgeklebt aus. */
.lm-report .lm-glas{
  background:linear-gradient(160deg,#fff 6%,color-mix(in srgb,var(--color-navy-soft) 88%,#fff) 94%);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,.95),
    inset 0 0 0 1px color-mix(in srgb,var(--color-navy) 12%,transparent),
    0 1px 2px rgba(20,22,31,.06),
    0 4px 10px -4px rgba(20,22,31,.12);
}
/* Nur auf echten Zeigegeräten, sonst löst eine Berührung den Zustand aus und er bleibt
   hängen. Kurz und ease-out, damit es antwortet statt zu schweben. */
@media (hover:hover) and (pointer:fine){
  .lm-report .lm-hero article{transition:transform 160ms cubic-bezier(.23,1,.32,1),box-shadow 160ms cubic-bezier(.23,1,.32,1)}
  .lm-report .lm-hero article:hover{transform:translateY(-1px)}
  .lm-report .lm-hero article:hover .lm-glas{
    box-shadow:
      inset 0 1px 0 rgba(255,255,255,1),
      inset 0 0 0 1px color-mix(in srgb,var(--color-navy) 20%,transparent),
      0 2px 4px rgba(20,22,31,.07),
      0 8px 18px -6px rgba(20,22,31,.16);
  }
}
@media (prefers-reduced-motion: reduce){
  .lm-report .lm-hero article{transition:none}
  .lm-report .lm-hero article:hover{transform:none}
}
@media(max-width:639px){
 .lm-actions h2::before,.lm-plan p:first-child::before{width:28px;margin-bottom:11px}
}
`}</style>;
}
