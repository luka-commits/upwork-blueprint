// The eight stages a lead moves through, in pipeline order. code/pipeline.py
// STATUSES owns the keys; the labels are fixed (website/PRINCIPLES.md).
export const ORDER = ['new', 'applied', 'replied', 'call', 'offer', 'won', 'lost', 'skipped'];
export const LABEL = {
  new: 'Not applied', applied: 'Applied', replied: 'In conversation', call: 'Call',
  offer: 'Offer', won: 'Won', lost: 'Lost', skipped: 'Skipped',
};
// The board is the part where a conversation is alive. Applied is not a stage a
// member works, it is waiting, and Lost is history; both are counted in Analytics
// and neither earns a column here. The list holds Not applied and Applied. A lead
// that is Lost or Skipped leaves both surfaces: it stays in the pipeline file and
// in the funnel, and nothing asks the member to look at it again.
export const BOARD = ['replied', 'call', 'offer', 'won'];
// The list decides: what has not been sent, and what was sent and is still silent.
export const LIST = ['new', 'applied'];
