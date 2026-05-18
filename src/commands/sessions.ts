import { Command } from 'commander';
import chalk from 'chalk';
import inquirer from 'inquirer';
import {
  listSessions,
  loadSession,
  deleteSession,
  formatDate,
  truncateString,
} from '../utils.js';

export const sessionsCommand = new Command('sessions')
  .description('Gestionar sesiones de chat');

sessionsCommand
  .command('list')
  .alias('ls')
  .description('Listar todas las sesiones')
  .action(() => {
    const sessions = listSessions();

    if (sessions.length === 0) {
      console.log(chalk.gray('\nNo tienes sesiones guardadas.\n'));
      console.log(chalk.cyan('Crea una con: ') + chalk.yellow('claudy chat\n'));
      return;
    }

    console.log(chalk.cyan.bold(`\n📋 Sesiones (${sessions.length}):\n`));

    sessions.forEach((session) => {
      console.log(chalk.yellow(`▸ ${session.id.substring(0, 8)}`));
      console.log(`  ${chalk.bold(session.name)}`);
      console.log(chalk.gray(`  Modelo: ${session.model}`));
      console.log(chalk.gray(`  Mensajes: ${session.messages.length}`));
      console.log(chalk.gray(`  Actualizada: ${formatDate(session.updatedAt)}`));
      console.log('');
    });
  });

sessionsCommand
  .command('show <id>')
  .description('Mostrar contenido de una sesión')
  .action((id: string) => {
    const sessions = listSessions();
    const session = sessions.find((s) => s.id.startsWith(id)) || loadSession(id);

    if (!session) {
      console.log(chalk.red(`✗ Sesión "${id}" no encontrada.`));
      process.exit(1);
    }

    console.log(chalk.cyan.bold(`\n💬 ${session.name}\n`));
    console.log(chalk.gray(`ID: ${session.id}`));
    console.log(chalk.gray(`Modelo: ${session.model}`));
    console.log(chalk.gray(`Creada: ${formatDate(session.createdAt)}`));
    console.log(chalk.gray(`Mensajes: ${session.messages.length}\n`));
    console.log(chalk.gray('─────────────────────────────────────────\n'));

    session.messages.forEach((msg) => {
      const prefix = msg.role === 'user' ? chalk.green('You:') : chalk.blue('Claudy:');
      console.log(`${prefix} ${msg.content}\n`);
    });
  });

sessionsCommand
  .command('delete <id>')
  .alias('rm')
  .description('Eliminar una sesión')
  .option('-f, --force', 'No pedir confirmación')
  .action(async (id: string, options) => {
    const sessions = listSessions();
    const session = sessions.find((s) => s.id.startsWith(id));

    if (!session) {
      console.log(chalk.red(`✗ Sesión "${id}" no encontrada.`));
      process.exit(1);
    }

    if (!options.force) {
      const { confirm } = await inquirer.prompt([
        {
          type: 'confirm',
          name: 'confirm',
          message: `¿Eliminar sesión "${session.name}"?`,
          default: false,
        },
      ]);

      if (!confirm) {
        console.log(chalk.gray('Cancelado.'));
        return;
      }
    }

    if (deleteSession(session.id)) {
      console.log(chalk.green(`✓ Sesión "${session.name}" eliminada.`));
    } else {
      console.log(chalk.red('✗ No se pudo eliminar.'));
    }
  });

sessionsCommand
  .command('export <id>')
  .description('Exportar sesión a markdown')
  .option('-o, --output <file>', 'Archivo de salida')
  .action((id: string, options) => {
    const sessions = listSessions();
    const session = sessions.find((s) => s.id.startsWith(id)) || loadSession(id);

    if (!session) {
      console.log(chalk.red(`✗ Sesión "${id}" no encontrada.`));
      process.exit(1);
    }

    let markdown = `# ${session.name}\n\n`;
    markdown += `- **ID**: ${session.id}\n`;
    markdown += `- **Modelo**: ${session.model}\n`;
    markdown += `- **Creada**: ${formatDate(session.createdAt)}\n`;
    markdown += `- **Mensajes**: ${session.messages.length}\n\n`;
    markdown += '---\n\n';

    session.messages.forEach((msg) => {
      const role = msg.role === 'user' ? '**You**' : '**Claudy**';
      markdown += `### ${role}\n\n${msg.content}\n\n`;
    });

    if (options.output) {
      const fs = require('fs');
      fs.writeFileSync(options.output, markdown, 'utf-8');
      console.log(chalk.green(`✓ Exportado a: ${options.output}`));
    } else {
      console.log(markdown);
    }
  });
