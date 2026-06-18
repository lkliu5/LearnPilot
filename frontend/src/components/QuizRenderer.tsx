import { useState } from 'react'

export interface QuizOption {
  option_id: string
  option_text: string
}

export interface QuizQuestion {
  question_id: string
  question_type: 'single' | 'multiple' | 'boolean' | 'short_answer'
  question_text: string
  options: QuizOption[]
  /** 客观题：option_id / option_id[]；简答题（short_answer）：参考要点 string[] */
  correct_answer: string | string[]
  /** 客观题：解析；简答题：参考答案 */
  explanation: string
}

/** 简答题 AI 评分（接口文档 9.1 shortAnswers[]）：0-100 分 + 简短点评 */
export interface ShortAnswerGrade {
  questionId: string
  score: number
  comment: string
}

/** 提交后由父级回填的综合判分结果（联调取后端，mock 本地合成）。 */
export interface QuizGrade {
  /** 综合得分 0-100（客观题 + 简答 AI 折算） */
  score: number
  passed: boolean
  shortAnswers: ShortAnswerGrade[]
}

const arraysEqual = (a: string[], b: string[]) =>
  a.length === b.length && [...a].sort().join(',') === [...b].sort().join(',')

const typeLabel: Record<QuizQuestion['question_type'], string> = {
  single: '单选',
  multiple: '多选',
  boolean: '判断',
  short_answer: '简答',
}

const isShort = (q: QuizQuestion) => q.question_type === 'short_answer'

interface QuizRendererProps {
  questions: QuizQuestion[]
  /**
   * 上报错题（错题驱动再生成）；submitted=true 表示真实提交（非重做清空）。
   * 第三参 answers 为本次作答全集（question_id → 选项/文本），供联调提交给后端判分；
   * wrong 仅含客观错题（简答另由 AI 评分，不进错题强化）。
   */
  onSubmitResult?: (
    wrong: QuizQuestion[],
    submitted?: boolean,
    answers?: Record<string, string | string[]>
  ) => void
  /** 综合判分结果（含简答 AI 评分/点评）：提交后由父级回填，未回填时简答显示「评分中」。 */
  grade?: QuizGrade | null
}

export default function QuizRenderer({ questions, onSubmitResult, grade }: QuizRendererProps) {
  const [answers, setAnswers] = useState<Record<string, string | string[]>>({})
  const [submitted, setSubmitted] = useState(false)

  const objectiveQs = questions.filter((q) => !isShort(q))

  const setAnswer = (id: string, ans: string | string[]) =>
    setAnswers((prev) => ({ ...prev, [id]: ans }))

  const toggleMulti = (id: string, optId: string, checked: boolean) => {
    const cur = (answers[id] as string[]) || []
    setAnswer(id, checked ? [...cur, optId] : cur.filter((x) => x !== optId))
  }

  const isAnswered = (q: QuizQuestion) => {
    const a = answers[q.question_id]
    if (isShort(q)) return typeof a === 'string' && a.trim().length > 0
    return a != null
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

  const answeredCount = questions.filter(isAnswered).length
  const objectiveScore = objectiveQs.filter(isCorrect).length
  const shortGradeFor = (id: string) => grade?.shortAnswers.find((s) => s.questionId === id)

  return (
    <div className="quiz-container">
      {submitted && (
        <div className={`quiz-result ${grade?.passed ? 'quiz-result--perfect' : ''}`}>
          {grade ? (
            <>
              <span className="quiz-result__score">{grade.score}分</span>
              <span className="quiz-result__label">
                {grade.passed
                  ? '综合 ≥ 60，已通过并点亮「已掌握」！'
                  : `综合 ${grade.score} 分（未达 60），查看解析继续巩固`}
              </span>
            </>
          ) : (
            <>
              <span className="quiz-result__score">{objectiveScore}/{objectiveQs.length}</span>
              <span className="quiz-result__label">客观题已记录，简答题 AI 评分中…</span>
            </>
          )}
        </div>
      )}

      {questions.map((q, idx) => {
        if (isShort(q)) {
          const sg = submitted ? shortGradeFor(q.question_id) : undefined
          const text = (answers[q.question_id] as string) || ''
          const points = Array.isArray(q.correct_answer) ? q.correct_answer : []
          return (
            <div key={q.question_id} className="quiz-question quiz-question--short">
              <div className="quiz-question__head">
                <span className="quiz-question__badge">{typeLabel.short_answer}</span>
                <h3 className="quiz-question__text">{idx + 1}. {q.question_text}</h3>
              </div>

              <textarea
                className="quiz-short__input"
                value={text}
                disabled={submitted}
                rows={4}
                placeholder="用自己的话作答，AI 将对照参考要点为你评分…"
                onChange={(e) => setAnswer(q.question_id, e.target.value)}
              />

              {submitted && (
                <div className="quiz-ai">
                  {sg ? (
                    <div className="quiz-ai__head">
                      <span className="quiz-ai__badge">AI 评分</span>
                      <span className={`quiz-ai__score ${sg.score >= 60 ? 'is-pass' : 'is-low'}`}>
                        {sg.score} 分
                      </span>
                      <span className="quiz-ai__comment">{sg.comment}</span>
                    </div>
                  ) : (
                    <p className="quiz-ai__pending">AI 正在对照参考要点评分…</p>
                  )}
                  {points.length > 0 && (
                    <div className="quiz-ai__points">
                      <strong>参考要点：</strong>{points.join('；')}
                    </div>
                  )}
                  {q.explanation && (
                    <div className="quiz-explanation">
                      <strong>参考答案：</strong>{q.explanation}
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        }

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
            onSubmitResult?.(objectiveQs.filter((q) => !isCorrect(q)), true, answers)
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
