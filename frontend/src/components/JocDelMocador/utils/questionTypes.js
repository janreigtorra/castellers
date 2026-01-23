// Question type detection utilities

export const isSliderQuestion = (question) => {
  return question && question.slider_min !== undefined && question.slider_max !== undefined;
};

export const isMultipleOptionsQuestion = (question) => {
  return question && 
         Array.isArray(question.options) && 
         Array.isArray(question.correct_answer) &&
         question.correct_answer.length > 0;
};

export const isOrderingQuestion = (question) => {
  return question && 
         Array.isArray(question.options) && 
         Array.isArray(question.correct_answer_order) &&
         question.correct_answer_order.length > 0;
};

