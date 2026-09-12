function clean(value) {
  return String(value || '').replace(/\r/g, '').trim();
}

function withoutTitle(value) {
  return clean(value).replace(/^\s*#{1,6}\s*(?:application|cover letter)\s*\n+/i, '').trim();
}

export function parseApplication(value) {
  const source = clean(value);
  const screening = /^\s*#{1,6}\s*screening answers?\s*$/im.exec(source);
  const coverLetter = withoutTitle(screening ? source.slice(0, screening.index) : source);
  const answersSource = screening
    ? source.slice(screening.index + screening[0].length).trim()
    : '';
  const headings = [...answersSource.matchAll(/^\s*#{2,6}\s+(.+?)\s*$/gm)];

  if (!answersSource) return { coverLetter, answers: [] };
  if (!headings.length) {
    return { coverLetter, answers: [{ question: 'Screening answers', answer: answersSource }] };
  }

  const answers = headings.map((heading, index) => {
    const start = Number(heading.index) + heading[0].length;
    const end = index + 1 < headings.length ? Number(headings[index + 1].index) : answersSource.length;
    return {
      question: clean(heading[1]),
      answer: clean(answersSource.slice(start, end)),
    };
  }).filter(item => item.question && item.answer);

  return { coverLetter, answers };
}
