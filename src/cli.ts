#!/usr/bin/env node

import { Command } from 'commander';
import { setupCommand } from './commands/setup.js';
import { chatCommand } from './commands/chat.js';
import { configCommand } from './commands/config.js';
import { sessionsCommand } from './commands/sessions.js';
import { modelsCommand } from './commands/models.js';
import { skillsCommand } from './commands/skills.js';

const program = new Command();

program
  .name('claudy')
  .description('Personal AI Assistant CLI')
  .version('0.1.0');

// Comandos principales
program.addCommand(setupCommand);
program.addCommand(chatCommand);
program.addCommand(configCommand);
program.addCommand(sessionsCommand);
program.addCommand(modelsCommand);
program.addCommand(skillsCommand);

// Help personalizado
program.on('--help', () => {
  console.log('');
  console.log('Ejemplos:');
  console.log('  $ claudy setup           # Configurar Claudy por primera vez');
  console.log('  $ claudy chat            # Iniciar sesión de chat interactivo');
  console.log('  $ claudy config get      # Ver configuración actual');
  console.log('  $ claudy models list     # Listar modelos disponibles');
  console.log('');
});

program.parse(process.argv);

if (!process.argv.slice(2).length) {
  program.outputHelp();
}
