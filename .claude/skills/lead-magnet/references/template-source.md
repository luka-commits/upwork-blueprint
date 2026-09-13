# Template source

The report shell comes from the Pocket CEO proposal lead magnet at source commit
`b86a6d8f9f5e8b32c9d81b72fed9fc044984edc0`. Git commit `880b0a9` in this
repository contains the byte-identical source snapshot before adaptation.

The vendored source lives in `template/src/proposal/`. The portable runtime in
`template/src/main.tsx` supplies report data and Vite builds the complete report
into `template/dist/index.html`.

Keep the original component structure, illustrations, scorecard, interactions
and visual system. Adapt only what an independent freelancer installation
requires:

- remove Pocket CEO names, logos and operator-specific links;
- remove tracking, pricing, calendars and off-platform contact routes;
- remove remote media fallbacks;
- map measured job evidence into the existing report data model;
- show missing evidence as missing, never as a fabricated result;
- end with an Upwork reply instruction.

The built file must remain self-contained. It may load data URI images and run
its bundled script. It must make no network request.
