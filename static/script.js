document.addEventListener('DOMContentLoaded', () => {
    const interviewForm = document.getElementById('interview-form');
    const resultsInput = document.getElementById('results-data-input');
    const intervieweeNameInput = document.getElementById('interviewee-name');
    const intervieweeNameHidden = document.getElementById('interviewee-name-hidden');
    const finishBtn = document.getElementById('finish-btn');
    const resetBtn = document.getElementById('reset-btn');
    const mainContainer = document.getElementById('main-interview-container');
    const addThemeBtn = document.getElementById('add-theme-btn');

    const isQuestionsPage = window.location.pathname.includes('/questions');
    let results = {};

    if (!isQuestionsPage && interviewForm) {
        document.querySelectorAll('.question-block').forEach(block => {
            block.style.cursor = 'pointer';
            block.addEventListener('click', (e) => {
                if (e.target.closest('.controls, a, details')) {
                    return;
                }
                const details = block.querySelector('details');
                if (details) {
                    details.open = !details.open;
                }
            });
        });

        const initRatingButtons = (container) => {
            container.querySelectorAll('.control-btn').forEach(button => {
                button.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const button = e.currentTarget;
                    const block = button.closest('.question-block');
                    const questionId = block.dataset.questionId;
                    const value = button.dataset.value;
                    results[questionId] = value;
                    block.querySelectorAll('.control-btn').forEach(btn => btn.classList.remove('ring-2', 'ring-blue-500'));
                    button.classList.add('ring-2', 'ring-blue-500');
                });
            });
        };
        initRatingButtons(document.body);

        if (finishBtn) {
            finishBtn.addEventListener('click', () => {
                resultsInput.value = JSON.stringify(results);
                intervieweeNameHidden.value = intervieweeNameInput.value;
                interviewForm.submit();
            });
        }
        if (resetBtn) {
            resetBtn.addEventListener('click', () => {
                results = {};
                document.querySelectorAll('.control-btn').forEach(btn => btn.classList.remove('ring-2', 'ring-blue-500'));
                intervieweeNameInput.value = '';
                console.log("Голосование сброшено.");
            });
        }
    }

    const initThemeToggle = (container) => {
        container.querySelectorAll('.theme-header').forEach(header => {
            header.addEventListener('click', (e) => {
                if (e.target.closest('.delete-theme-btn, [contenteditable="true"]')) {
                    return;
                }
                const themeContainer = header.closest('.theme-container');
                const content = themeContainer.querySelector('.theme-content');
                const icon = header.querySelector('.toggle-icon');

                content.classList.toggle('hidden');
                themeContainer.classList.toggle('collapsed');
                icon.classList.toggle('rotate-180');
            });
        });
    };
    initThemeToggle(document.body);

    if (isQuestionsPage && mainContainer) {
        const sendQuestionOrderUpdate = () => {
            const payload = { themes: [], unthemed: [] };
            document.querySelectorAll('.theme-container').forEach(container => {
                const themeId = container.dataset.themeId;
                const order = Array.from(container.querySelectorAll('.question-block')).map(b => b.dataset.questionId);
                payload.themes.push({ id: themeId, order: order });
            });
            const unthemedContainer = document.getElementById('unthemed-questions-container');
            if (unthemedContainer) {
                payload.unthemed = Array.from(unthemedContainer.querySelectorAll('.question-block')).map(b => b.dataset.questionId);
            }
            fetch('/update_positions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            }).then(res => res.json()).then(data => {
                if (data.success) console.log('Порядок вопросов сохранен.');
                else console.error('Ошибка сохранения порядка вопросов:', data.error);
            });
        };

        const sendThemeOrderUpdate = () => {
            const order = Array.from(mainContainer.querySelectorAll('.theme-container')).map(c => c.dataset.themeId);
            fetch('/update_theme_order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ order: order })
            }).then(res => res.json()).then(data => {
                if (data.success) console.log('Порядок тем сохранен.');
                else console.error('Ошибка сохранения порядка тем:', data.error);
            });
        };

        const initSortable = () => {
            document.querySelectorAll('.questions-list').forEach(list => {
                new Sortable(list, {
                    group: 'shared-questions',
                    animation: 150,
                    ghostClass: 'sortable-ghost',
                    onEnd: sendQuestionOrderUpdate
                });
            });

            new Sortable(mainContainer, {
                group: 'shared-themes',
                animation: 150,
                handle: '.theme-header',
                ghostClass: 'sortable-ghost-theme',
                onEnd: sendThemeOrderUpdate
            });
        };
        initSortable();

        const initThemeTitleEditing = (titleElement) => {
            titleElement.addEventListener('blur', (e) => {
                const themeContainer = e.target.closest('.theme-container');
                const themeId = themeContainer.dataset.themeId;
                const newName = e.target.textContent.trim();
                if (!newName) { e.target.textContent = 'Новая тема'; return; }
                fetch('/update_theme_name', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: themeId, name: newName })
                }).then(res => res.json()).then(data => {
                    if (data.success) console.log(`Название темы ${themeId} обновлено.`);
                    else alert(`Ошибка: ${data.error}`);
                });
            });
            titleElement.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); e.target.blur(); } });
        };
        document.querySelectorAll('.theme-title-editable').forEach(initThemeTitleEditing);

        const initThemeDeletion = (deleteButton) => {
            deleteButton.addEventListener('click', (e) => {
                if (!confirm('Вы уверены? Вопросы из этой темы станут "без темы".')) return;
                const themeContainer = e.target.closest('.theme-container');
                const themeId = themeContainer.dataset.themeId;
                fetch(`/delete_theme/${themeId}`, { method: 'POST' }).then(res => res.json()).then(data => {
                    if (data.success) {
                        const unthemedContainer = document.getElementById('unthemed-questions-container');
                        themeContainer.querySelectorAll('.question-block').forEach(q => unthemedContainer.appendChild(q));
                        themeContainer.remove();
                        console.log(`Тема ${themeId} удалена.`);
                    } else alert(`Ошибка: ${data.error}`);
                });
            });
        };
        document.querySelectorAll('.delete-theme-btn').forEach(initThemeDeletion);

        if (addThemeBtn) {
            addThemeBtn.addEventListener('click', () => {
                const themeName = prompt("Название новой темы:", "Новая тема");
                if (!themeName || !themeName.trim()) return;
                fetch('/add_theme', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: themeName.trim() })
                }).then(res => res.json()).then(data => {
                    if (data.success) {
                        window.location.reload();
                    } else alert(`Ошибка: ${data.error}`);
                });
            });
        }

        const initQuestionEditing = (questionBlock) => {
            const questionId = questionBlock.dataset.questionId;
            const titleEl = questionBlock.querySelector('.question-title');
            const answerEl = questionBlock.querySelector('.question-answer');
            const editBtn = questionBlock.querySelector('.edit-question-btn');
            const saveBtn = questionBlock.querySelector('.save-question-btn');
            const cancelBtn = questionBlock.querySelector('.cancel-edit-btn');
            const deleteBtn = questionBlock.querySelector('.delete-btn');

            let originalTitleHTML = titleEl.innerHTML;
            let originalAnswerHTML = answerEl.innerHTML;

            editBtn.addEventListener('click', () => {
                titleEl.setAttribute('contenteditable', 'true');
                answerEl.setAttribute('contenteditable', 'true');
                titleEl.classList.add('outline', 'outline-2', 'outline-blue-400', 'rounded-md');
                answerEl.classList.add('outline', 'outline-2', 'outline-blue-400', 'rounded-md');

                editBtn.classList.add('hidden');
                deleteBtn.classList.add('hidden');
                saveBtn.classList.remove('hidden');
                cancelBtn.classList.remove('hidden');

                titleEl.focus();
            });

            cancelBtn.addEventListener('click', () => {
                titleEl.innerHTML = originalTitleHTML;
                answerEl.innerHTML = originalAnswerHTML;

                titleEl.setAttribute('contenteditable', 'false');
                answerEl.setAttribute('contenteditable', 'false');
                titleEl.classList.remove('outline', 'outline-2', 'outline-blue-400', 'rounded-md');
                answerEl.classList.remove('outline', 'outline-2', 'outline-blue-400', 'rounded-md');

                saveBtn.classList.add('hidden');
                cancelBtn.classList.add('hidden');
                editBtn.classList.remove('hidden');
                deleteBtn.classList.remove('hidden');
            });

            saveBtn.addEventListener('click', () => {
                const newTitle = titleEl.innerHTML;
                const newAnswer = answerEl.innerHTML;

                fetch(`/update_question/${questionId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title: newTitle, answer: newAnswer })
                })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        originalTitleHTML = newTitle;
                        originalAnswerHTML = newAnswer;
                        cancelBtn.click();
                        console.log(`Вопрос ${questionId} успешно обновлен.`);

                    } else {
                        alert(`Ошибка сохранения: ${data.error}`);
                    }
                })
                .catch(err => {
                    console.error('Fetch Error:', err);
                    alert('Произошла сетевая ошибка. Попробуйте снова.');
                });
            });
        };
        document.querySelectorAll('.question-block').forEach(initQuestionEditing);
    }

    let currentQuestionId = null;
    document.querySelectorAll('.delete-btn').forEach(button => {
        button.addEventListener('click', () => {
            currentQuestionId = button.dataset.questionId;
            document.getElementById('delete-modal').classList.remove('hidden');
        });
    });
    const cancelDeleteBtn = document.getElementById('cancel-delete');
    if (cancelDeleteBtn) cancelDeleteBtn.addEventListener('click', () => {
        document.getElementById('delete-modal').classList.add('hidden');
        currentQuestionId = null;
    });
    const confirmDeleteBtn = document.getElementById('confirm-delete');
    if (confirmDeleteBtn) confirmDeleteBtn.addEventListener('click', () => {
        if (currentQuestionId) {
            fetch(`/delete_question/${currentQuestionId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            }).then(res => res.json()).then(data => {
                if (data.success) window.location.reload();
            }).catch(error => console.error('Ошибка:', error));
        }
    });
});