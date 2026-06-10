import { useState } from 'react'

export interface QuizOption {
  option_id: string
  option_text: string
}

export interface QuizQuestion {
  question_id: string
  question_type: 'single' | 'multiple' | 'boolean'
  question_text: string
  options: QuizOption[]
  correct_answer: string | string[]
  explanation: string
}

const arraysEqual = (a: string[], b: string[]) =>
  a.length === b.length && [...a].sort().join(',') === [...b].sort().join(',')

const typeLabel: Record<QuizQuestion['question_type'], string> = {
  single: '单选',
  multiple: '多选',
  boolean: '判断',
}

interface QuizRendererProps {
  questions: QuizQuestion[]
  /**
   * 上报错题（错题驱动再生成）；submitted=true 表示真实提交（非重做清空）。
   * 第三参 answers 为本次作答全集（question_id → 选项），供联调提交给后端判分；
   * mock 模式可忽略，组件本地判分行为不变。
   */
  onSubmitResult?: (
    wrong: QuizQuestion[],
    submitted?: boolean,
    answers?: Record<string, string | string[]>
  ) => void
}

export default function QuizRenderer({ questions, onSubmitResult }: QuizRendererProps) {
  const [answers, setAnswers] = useState<Record<string, string | string[]>>({})
  const [submitted, setSubmitted] = useState(false)

  const setAnswer = (id: string, ans: string | string[]) =>
    setAnswers((prev) => ({ ...prev, [id]: ans }))

  const toggleMulti = (id: string, optId: string, checked: boolean) => {
    const cur = (answers[id] as string[]) || []
    setAnswer(id, checked ? [...cur, optId] : cur.filter((x) => x !== optId))
  }

  const isCorrect = (q: QuizQuestion) => {
    const a = answers[q.question_id]
    if (a == null) return false
    return Array.isArray(q.correct_answer)
      ? Array.isArray(a) && arraysEqual(a, q.correct_answer)
      : a === q.correct_answer
  }

  const optionPicked = (q: QuizQuestion, optId: string) => {
    const a = answers[q.question_id]
    return Array.isArray(a) ? a.includes(optId) : a === optId
  }

  const optionIsAnswer = (q: QuizQuestion, optId: string) =>
    Array.isArray(q.correct_answer) ? q.correct_answer.includes(optId) : q.correct_answer === optId

  const answeredCount = questions.filter((q) => answers[q.question_id] != null).length
  const score = questions.filter(isCorrect).length

  return (
    <div className="quiz-container">
      {submitted && (
        <div className={`quiz-result ${score === questions.length ? 'quiz-result--perfect' : ''}`}>
          <span className="quiz-result__score">{score}/{questions.length}</span>
          <span className="quiz-result__label">
            {score === questions.length ? '全部正确，掌握扎实！' : `答对 ${score} 题，查看解析继续巩固`}
          </span>
        </div>
      )}

      {questions.map((q, idx) => {
        const correct = isCorrect(q)
        return (
          <div
            key={q.question_id}
            className={`quiz-question ${submitted ? (correct ? 'quiz-question--correct' : 'quiz-question--wrong') : ''}`}
          >
            <div className="quiz-question__head">
              <span className="quiz-question__badge">{typeLabel[q.question_type]}</span>
              <h3 className="quiz-question__text">{idx + 1}. {q.question_text}</h3>
            </div>

            <div className="quiz-options">
              {q.options.map((opt) => {
                const picked = optionPicked(q, opt.option_id)
                const isAns = optionIsAnswer(q, opt.option_id)
                const cls = submitted
                  ? isAns
                    ? 'quiz-option--answer'
                    : picked
                      ? 'quiz-option--wrong'
                      : ''
                  : picked
                    ? 'quiz-option--picked'
                    : ''
                return (
                  <label key={opt.option_id} className={`quiz-option ${cls}`}>
                    <input
                      type={q.question_type === 'multiple' ? 'checkbox' : 'radio'}
                      name={q.question_id}
                      checked={picked}
                      disabled={submitted}
                      onChange={(e) =>
                        q.question_type === 'multiple'
                          ? toggleMulti(q.question_id, opt.option_id, e.target.checked)
                          : setAnswer(q.question_id, opt.option_id)
                      }
                    />
                    <span>{opt.option_text}</span>
                    {submitted && isAns && <span className="quiz-option__mark">✓</span>}
                  </label>
                )
              })}
            </div>

            {submitted && (
              <div className="quiz-explanation">
                <strong>解析：</strong>{q.explanation}
              </div>
            )}
          </div>
        )
      })}

      {!submitted ? (
        <button
          className="quiz-submit"
          disabled={answeredCount < questions.length}
          onClick={() => {
            setSubmitted(true)
            onSubmitResult?.(questions.filter((q) => !isCorrect(q)), true, answers)
          }}
        >
          {answeredCount < questions.length ? `还有 ${questions.length - answeredCount} 题未作答` : '提交答案'}
        </button>
      ) : (
        <button className="quiz-submit quiz-submit--retry" onClick={() => { setSubmitted(false); setAnswers({}); onSubmitResult?.([], false) }}>
          重新作答
        </button>
      )}
    </div>
  )
}
